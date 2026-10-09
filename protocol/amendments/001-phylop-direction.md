# Amendment 1: phyloP baseline direction, and one documentation correction

Date: 7 October 2026. Made before any GPU run or Evo 2 result.

## Change

The approved protocol specified "negated mammalian phyloP" as a baseline score. It now uses
mammalian phyloP without negation.

## Reason

Higher phyloP means stronger conservation, which predicts loss of function. Negating it scores
conserved positions as less damaging, which inverts the baseline. The error was found while
testing the analysis code on the Findlay table: the negated score gave AUROC 0.219 for all
3,893 SNVs, the mirror image of 0.781. The intent of the baseline (a conservation score that
predicts LOF) is unchanged.

## Effect

Only the sign of one baseline score changes. No Evo 2 workload, platform, metric, tolerance or
budget changes. The baseline values were computed before amendment because they need no GPU;
no Evo 2 output existed at that point.

## Documentation correction

The platform rationale said a RunPod BAA "needs a negotiated agreement and committed spend". The
spend condition came from a secondary summary and could not be confirmed from a public primary
source. The text now says RunPod states a BAA can be executed and that its terms were not
confirmed. The platform choice is unchanged.

## Approval

Approved by Tim Richardson on 9 October 2026.
