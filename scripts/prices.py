"""Record list prices for each completed platform at run time, from the providers' own APIs.

AWS: Price List API (on-demand Linux). Google Cloud: Cloud Billing Catalog API (Spot SKUs for the
machine's cores, memory and GPU). RunPod: the pod's own costPerHr. Disk prices are added per hour.
Writes prices.json next to the platform outputs; collect.py turns these into costs.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

HOURS_PER_MONTH = 730
# Disk list prices (USD per month), us-east-1 and us-central1, retrieved 7 October 2026 from
# https://aws.amazon.com/ebs/pricing/ and https://cloud.google.com/compute/disks-image-pricing
# RunPod container disk: https://www.runpod.io/pricing
EBS_GP3 = {"gb": 0.08, "iops_over_3000": 0.005, "mbps_over_125": 0.040}
GCE_PD_SSD_GB = 0.17
RUNPOD_CONTAINER_DISK_GB = 0.10


def run(*cmd: str) -> str:
    return subprocess.check_output(cmd, text=True).strip()


def aws_price(instance: dict, disk: dict) -> dict:
    region = instance["region"]
    filters = [("instanceType", instance["instance_type"]), ("regionCode", region), ("operatingSystem", "Linux"),
               ("tenancy", "Shared"), ("preInstalledSw", "NA"), ("capacitystatus", "Used")]
    args = ["aws", "pricing", "get-products", "--region", "us-east-1", "--service-code", "AmazonEC2",
            "--output", "json", "--filters"] + [f"Type=TERM_MATCH,Field={k},Value={v}" for k, v in filters]
    products = json.loads(run(*args))["PriceList"]
    if len(products) != 1:
        raise RuntimeError(f"Expected one AWS price for {instance['instance_type']}, got {len(products)}")
    terms = json.loads(products[0])["terms"]["OnDemand"]
    dimension = next(iter(next(iter(terms.values()))["priceDimensions"].values()))
    hourly = float(dimension["pricePerUnit"]["USD"])
    storage = (disk["gb"] * EBS_GP3["gb"] + max(0, disk["iops"] - 3000) * EBS_GP3["iops_over_3000"]
               + max(0, disk["mbps"] - 125) * EBS_GP3["mbps_over_125"]) / HOURS_PER_MONTH
    return {"instance_usd_per_hour": hourly, "storage_usd_per_hour": round(storage, 4),
            "source": f"AWS Price List API, on-demand Linux, {region}"}


def gcp_skus(token: str) -> list[dict]:
    skus, page = [], ""
    while True:
        query = urllib.parse.urlencode({"currencyCode": "USD", "pageSize": 5000, "pageToken": page})
        request = urllib.request.Request(
            f"https://cloudbilling.googleapis.com/v1/services/6F81-5844-456A/skus?{query}",
            headers={"Authorization": f"Bearer {token}"})
        body = json.load(urllib.request.urlopen(request, timeout=60))
        skus += body.get("skus", [])
        page = body.get("nextPageToken", "")
        if not page:
            return skus


def sku_unit_price(sku: dict) -> float:
    expression = sku["pricingInfo"][0]["pricingExpression"]
    rate = expression["tieredRates"][-1]["unitPrice"]
    return int(rate.get("units", 0)) + rate.get("nanos", 0) / 1e9


def gcp_price(instance: dict, project: str) -> dict:
    region, zone = instance["region"], instance["zone"]
    machine = json.loads(run("gcloud", "compute", "machine-types", "describe", instance["instance_type"],
                             "--zone", zone, "--project", project, "--format", "json"))
    vcpus, memory_gib = machine["guestCpus"], machine["memoryMb"] / 1024
    token = run("gcloud", "auth", "print-access-token")
    spot = instance["purchase_option"] == "spot"
    regional = [s for s in gcp_skus(token) if region in s.get("serviceRegions", [])]
    in_region = [s for s in regional if (s["category"]["usageType"] == "Preemptible") == spot]

    def find(*words: str) -> dict:
        matches = [s for s in in_region if all(w.lower() in s["description"].lower() for w in words)]
        if len(matches) != 1:
            raise RuntimeError(f"Expected one SKU for {words} in {region}, got {[m['description'] for m in matches]}")
        return matches[0]

    family = instance["instance_type"].split("-")[0].upper()  # A3
    core, ram = find(f"{family} Instance Core"), find(f"{family} Instance Ram")
    gpu = find("H100 80GB GPU") if family == "A3" else None
    disk = [s for s in regional if s["description"].startswith("SSD backed PD Capacity")]
    hourly = vcpus * sku_unit_price(core) + memory_gib * sku_unit_price(ram) + (sku_unit_price(gpu) if gpu else 0)
    disk_month = sku_unit_price(disk[0]) if disk else GCE_PD_SSD_GB
    return {"instance_usd_per_hour": round(hourly, 4),
            "storage_usd_per_hour": round(instance["disk_gb"] * disk_month / HOURS_PER_MONTH, 4),
            "source": f"Cloud Billing Catalog API, {'Spot' if spot else 'on-demand'}, {region}: "
                      f"{vcpus} vCPU x {core['description']}, {memory_gib:.0f} GiB x {ram['description']}"
                      + (f", 1 x {gpu['description']}" if gpu else ""),
            "skus": [s["skuId"] for s in (core, ram, gpu) if s]}


def runpod_price(instance: dict) -> dict:
    return {"instance_usd_per_hour": instance["cost_per_hr"],
            "storage_usd_per_hour": round(instance["disk_gb"] * RUNPOD_CONTAINER_DISK_GB / HOURS_PER_MONTH, 4),
            "source": "RunPod pod costPerHr returned by the REST API at launch"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--gcp-project")
    args = parser.parse_args()
    prices = {"retrieved_utc": dt.datetime.now(dt.UTC).isoformat()}
    for instance_file in sorted(args.output.glob("platforms/*/attempt-*/instance.json")):
        pid = instance_file.parts[-3]
        instance = json.loads(instance_file.read_text())
        try:
            if instance["provider"] == "aws":
                prices[pid] = aws_price(instance, {"gb": instance["disk_gb"], "iops": 6000, "mbps": 500})
            elif instance["provider"] == "gcp":
                prices[pid] = gcp_price(instance, args.gcp_project)
            elif instance["provider"] == "runpod":
                prices[pid] = runpod_price(instance)
        except Exception as error:  # record and continue; a missing price is reported, not guessed
            prices[pid] = {"instance_usd_per_hour": None, "error": str(error)}
    (args.output / "prices.json").write_text(json.dumps(prices, indent=2) + "\n")
    print(json.dumps(prices, indent=2))


if __name__ == "__main__":
    main()
