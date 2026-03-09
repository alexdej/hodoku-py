/*
 * C accelerator for the generalized fish cover-combination search.
 *
 * 81-bit candidate masks are split into lo (bits 0-63) and hi (bits 64-80),
 * matching Java's M1/M2 representation.
 *
 * Compile:
 *   gcc -O2 -shared -fPIC -o _fish_accel.so _fish_accel.c
 *
 * Called from fish.py via ctypes.
 */

#include <stdint.h>
#include <string.h>

/* ---- 81-bit mask helpers ---- */

typedef struct { uint64_t lo, hi; } M81;

static const uint64_t HI_MASK = ((uint64_t)1 << 17) - 1;

static inline M81 m_or(M81 a, M81 b)     { return (M81){a.lo|b.lo, a.hi|b.hi}; }
static inline M81 m_and(M81 a, M81 b)    { return (M81){a.lo&b.lo, a.hi&b.hi}; }
static inline M81 m_andnot(M81 a, M81 b) { return (M81){a.lo & ~b.lo, a.hi & ~b.hi}; }
static inline int m_zero(M81 m)           { return m.lo == 0 && m.hi == 0; }
static inline int m_popcnt(M81 m) {
    return __builtin_popcountll(m.lo) + __builtin_popcountll(m.hi);
}

/* ---- BUDDIES table (set once from Python) ---- */

static M81 buddies[81];

void fish_set_buddy(int cell, uint64_t lo, uint64_t hi) {
    buddies[cell] = (M81){lo, hi & HI_MASK};
}

static M81 fin_buddies(M81 fins) {
    M81 result = {~(uint64_t)0, HI_MASK};
    uint64_t lo = fins.lo, hi = fins.hi;
    while (lo) {
        int bit = __builtin_ctzll(lo);
        result = m_and(result, buddies[bit]);
        lo &= lo - 1;
    }
    while (hi) {
        int bit = 64 + __builtin_ctzll(hi);
        result = m_and(result, buddies[bit]);
        hi &= hi - 1;
    }
    return result;
}

/* ---- Result structure ---- */

typedef struct {
    int32_t indices[7]; /* picked cover indices, 0-based */
    uint64_t cover_lo, cover_hi;
    uint64_t cannibal_lo, cannibal_hi;
    uint64_t fins_lo, fins_hi;
    uint64_t elim_lo, elim_hi;
} FishResult;

/* ---- Main search function ----
 *
 * Returns the number of valid fish combos found.
 * Results are written into `out` (up to max_out entries).
 */
int fish_find_covers(
    const uint64_t *ce_lo,      /* cover-eligible masks (lo halves) */
    const uint64_t *ce_hi,      /* cover-eligible masks (hi halves) */
    int num_cover,              /* number of eligible cover units    */
    int n,                      /* fish size (choose n)              */
    uint64_t base_lo,           /* base candidate mask               */
    uint64_t base_hi,
    uint64_t cand_lo,           /* full candidate set for this digit */
    uint64_t cand_hi,
    int with_fins,
    int max_fins,
    FishResult *out,
    int max_out
) {
    M81 base = {base_lo, base_hi & HI_MASK};
    M81 cand = {cand_lo, cand_hi & HI_MASK};
    int count = 0;

    /* DFS stack (level 0 = sentinel, levels 1..n = active) */
    M81 cc[8] = {{0,0}};  /* cover_cand  */
    M81 cn[8] = {{0,0}};  /* cannibalistic */
    int ni[8] = {0};       /* next index   */
    int pi[8] = {0};       /* picked index */

    int level = 1;
    ni[1] = 0;

    for (;;) {
        /* Backtrack if not enough remaining units */
        while (ni[level] > num_cover - (n - level + 1)) {
            if (--level == 0) goto done;
        }

        int ci = ni[level]++;
        pi[level] = ci;

        M81 mask = {ce_lo[ci], ce_hi[ci] & HI_MASK};
        M81 prev = cc[level - 1];
        M81 new_cand = m_or(prev, mask);
        M81 overlap = m_and(prev, mask);
        M81 new_cannibal = cn[level - 1];
        if (!m_zero(overlap))
            new_cannibal = m_or(new_cannibal, overlap);

        if (level < n) {
            /* Pruning: if fully covered already, no fins possible */
            if (with_fins && m_zero(m_andnot(base, new_cand)))
                continue;
            cc[level] = new_cand;
            cn[level] = new_cannibal;
            level++;
            ni[level] = ci + 1;
            continue;
        }

        /* --- Leaf: complete combination --- */
        M81 fins = m_andnot(base, new_cand);

        if (!with_fins) {
            if (!m_zero(fins)) continue;
            M81 elim = m_andnot(m_and(cand, new_cand), base);
            if (!m_zero(new_cannibal))
                elim = m_or(elim, m_and(cand, new_cannibal));
            if (m_zero(elim)) continue;

            if (count < max_out) {
                FishResult *r = &out[count];
                for (int k = 1; k <= n; k++) r->indices[k-1] = pi[k];
                r->cover_lo = new_cand.lo;   r->cover_hi = new_cand.hi;
                r->cannibal_lo = new_cannibal.lo; r->cannibal_hi = new_cannibal.hi;
                r->fins_lo = 0; r->fins_hi = 0;
                r->elim_lo = elim.lo; r->elim_hi = elim.hi;
            }
            count++;
        } else {
            int fc = m_popcnt(fins);
            if (fc == 0 || fc > max_fins) continue;

            M81 fb = fin_buddies(fins);
            M81 elim = m_andnot(m_and(m_and(cand, new_cand), fb), base);
            if (!m_zero(new_cannibal))
                elim = m_or(elim, m_and(m_and(cand, new_cannibal), fb));
            if (m_zero(elim)) continue;

            if (count < max_out) {
                FishResult *r = &out[count];
                for (int k = 1; k <= n; k++) r->indices[k-1] = pi[k];
                r->cover_lo = new_cand.lo;   r->cover_hi = new_cand.hi;
                r->cannibal_lo = new_cannibal.lo; r->cannibal_hi = new_cannibal.hi;
                r->fins_lo = fins.lo; r->fins_hi = fins.hi;
                r->elim_lo = elim.lo; r->elim_hi = elim.hi;
            }
            count++;
        }
    }
done:
    return count;
}
