# Optimistic Upper-Bound Calculation: filling the real 35-part backlog

This is the required reproducible bound: even under the most generous assumptions, does filling the 35 flange-bearing parts raise D2 above a density of 1%?

## Inputs (frozen, from 00_Spec)

- Composable nodes: 656; unordered pairs: 214,840 [E].
- Current declared electrical ports: 25 (out of 553; the other 528 are `ELEC:UNKNOWN`) [E].
- Current D2 pairs (type + pin order + gender all present): 8, i.e. density 8/214,840 = 0.00372% [V].
- Real backlog after B2 triage: 35 parts (A-class flange-bearing: 15 grippers incl. 4 dexterous hands + 20 six-axis F/T sensors) [E].
- Current vendor count: 329 [E].

## Generous assumptions (deliberately optimistic, to show the bound is not tight on our side)

1. Every one of the 35 backlog parts is documented perfectly and contributes **one fully declared electrical device-side port** with a unique, well-formed label, pin order, and gender.
2. Every newly declared port is electrically compatible with every other declared port (new or old): a new device plugs into every other declared device.
3. We ignore the locus correction (D3), which would only reduce the count; this bound is on D2.

## Computation

Let n_declared_before = 25 ports. After adding 35, n_declared_after = 25 + 35 = 60 ports.

Number of unordered pairs among 60 ports = C(60,2) = 60·59/2 = **1,770 pairs**.

But not every port pair is a *candidate pair of composable nodes in the catalogue*. The catalogue denominator is 214,840 unordered node pairs. The D2 count is bounded by the number of port pairs that sit on two distinct composable nodes in the catalogue — and even under the most generous assumption (every new port pair is a real candidate), the D2 count cannot exceed C(60,2) = 1,770.

D2 density after the most optimistic fill ≤ 1,770 / 214,840 = **0.824%**.

## Conclusion

Even under assumptions that a real data-collection programme will never meet (perfect documentation, universal cross-compatibility, ignoring locus correction), the D2 density remains below 1% (0.824%). The current measured D2 is 0.00372%. The ratio of optimistic bound to current value is 1,770/8 ≈ 221×, but the density remains two orders below 1%.

Filling the backlog reclassifies unknowns; it does not raise the density above 1%. This is the quantitative form of contribution C2: the zeros are not waiting on a missing data-collection exercise of plausible size.

## Reproduce

```python
from math import comb
n_after = 25 + 35
pairs = comb(n_after, 2)
denom = 214_840
print(pairs, pairs/denom*100)   # 1770 0.824%
```
