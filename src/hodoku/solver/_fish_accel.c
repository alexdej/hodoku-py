/*
 * Python C extension: generalized fish cover-combination search.
 *
 * 81-bit candidate masks are split into lo (bits 0-63) and hi (bits 64-80).
 *
 * Exported Python API:
 *   set_buddies(buddies: list[int]) -> None
 *   find_covers(ce_masks, n, base_cand, cand_set, with_fins, max_fins, endo_fins)
 *       -> list[tuple[tuple[int,...], int, int, int]]
 *          each entry: (indices, cover_mask, fins_mask, elim_mask)
 */

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>

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
    uint64_t fins_lo, fins_hi;
    uint64_t elim_lo, elim_hi;
} FishResult;

/* ---- Main search function ---- */

static int fish_find_covers(
    const uint64_t *ce_lo, const uint64_t *ce_hi,
    int num_cover, int n,
    uint64_t base_lo, uint64_t base_hi,
    uint64_t cand_lo, uint64_t cand_hi,
    int with_fins, int max_fins,
    uint64_t endo_lo, uint64_t endo_hi,
    FishResult *out, int max_out
) {
    M81 base = {base_lo, base_hi & HI_MASK};
    M81 cand = {cand_lo, cand_hi & HI_MASK};
    M81 endo = {endo_lo, endo_hi & HI_MASK};
    int count = 0;

    M81 cc[8] = {{0,0}};
    M81 cn[8] = {{0,0}};
    int ni[8] = {0};
    int pi[8] = {0};

    int level = 1;
    ni[1] = 0;

    for (;;) {
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
        M81 all_fins = m_or(fins, endo);

        if (!with_fins) {
            if (!m_zero(all_fins)) continue;
            M81 elim = m_andnot(m_and(cand, new_cand), base);
            if (!m_zero(new_cannibal))
                elim = m_or(elim, m_and(cand, new_cannibal));
            if (m_zero(elim)) continue;

            if (count < max_out) {
                FishResult *r = &out[count];
                for (int k = 1; k <= n; k++) r->indices[k-1] = pi[k];
                r->cover_lo = new_cand.lo; r->cover_hi = new_cand.hi;
                r->fins_lo = 0; r->fins_hi = 0;
                r->elim_lo = elim.lo; r->elim_hi = elim.hi;
            }
            count++;
        } else {
            int fc = m_popcnt(all_fins);
            if (fc == 0 || fc > max_fins) continue;

            M81 fb = fin_buddies(all_fins);
            M81 elim = m_andnot(m_and(m_and(cand, new_cand), fb), base);
            if (!m_zero(new_cannibal))
                elim = m_or(elim, m_and(m_and(cand, new_cannibal), fb));
            if (m_zero(elim)) continue;

            if (count < max_out) {
                FishResult *r = &out[count];
                for (int k = 1; k <= n; k++) r->indices[k-1] = pi[k];
                r->cover_lo = new_cand.lo; r->cover_hi = new_cand.hi;
                r->fins_lo = fins.lo; r->fins_hi = fins.hi;
                r->elim_lo = elim.lo; r->elim_hi = elim.hi;
            }
            count++;
        }
    }
done:
    return count;
}

/* ---- Python interface ---- */

/* Cached Python objects for 81-bit <-> lo/hi conversion */
static PyObject *_py_lo_mask = NULL;  /* (1 << 64) - 1 */
static PyObject *_py_64 = NULL;       /* 64 */

static int pylong_to_m81(PyObject *obj, M81 *out) {
    PyObject *lo_obj = PyNumber_And(obj, _py_lo_mask);
    if (!lo_obj) return -1;
    out->lo = PyLong_AsUnsignedLongLong(lo_obj);
    Py_DECREF(lo_obj);
    if (out->lo == (uint64_t)-1 && PyErr_Occurred()) return -1;

    PyObject *hi_obj = PyNumber_Rshift(obj, _py_64);
    if (!hi_obj) return -1;
    unsigned long long hi = PyLong_AsUnsignedLongLong(hi_obj);
    Py_DECREF(hi_obj);
    if (hi == (unsigned long long)-1 && PyErr_Occurred()) return -1;
    out->hi = (uint64_t)hi & HI_MASK;
    return 0;
}

static PyObject *m81_to_pylong(M81 m) {
    PyObject *hi_int = PyLong_FromUnsignedLongLong(m.hi);
    if (!hi_int) return NULL;
    PyObject *shifted = PyNumber_Lshift(hi_int, _py_64);
    Py_DECREF(hi_int);
    if (!shifted) return NULL;
    PyObject *lo_int = PyLong_FromUnsignedLongLong(m.lo);
    if (!lo_int) { Py_DECREF(shifted); return NULL; }
    PyObject *result = PyNumber_Or(shifted, lo_int);
    Py_DECREF(shifted);
    Py_DECREF(lo_int);
    return result;
}

/* set_buddies(buddies: list[int]) -> None */
static PyObject *py_set_buddies(PyObject *self, PyObject *arg) {
    if (!PyList_Check(arg) || PyList_GET_SIZE(arg) != 81) {
        PyErr_SetString(PyExc_ValueError, "expected list of 81 ints");
        return NULL;
    }
    for (int i = 0; i < 81; i++) {
        if (pylong_to_m81(PyList_GET_ITEM(arg, i), &buddies[i]) < 0)
            return NULL;
    }
    Py_RETURN_NONE;
}

/*
 * find_covers(ce_masks, n, base_cand, cand_set, with_fins, max_fins, endo_fins)
 *   -> list of (indices_tuple, cover_mask, fins_mask, elim_mask)
 */
static PyObject *py_find_covers(PyObject *self, PyObject *args) {
    PyObject *ce_list;
    int n, with_fins, max_fins;
    PyObject *base_obj, *cand_obj, *endo_obj;

    if (!PyArg_ParseTuple(args, "O!iOOiiO",
            &PyList_Type, &ce_list,
            &n,
            &base_obj, &cand_obj,
            &with_fins, &max_fins,
            &endo_obj))
        return NULL;

    Py_ssize_t num_cover = PyList_GET_SIZE(ce_list);
    if (num_cover == 0)
        return PyList_New(0);

    uint64_t *ce_lo = malloc(num_cover * sizeof(uint64_t));
    uint64_t *ce_hi = malloc(num_cover * sizeof(uint64_t));
    if (!ce_lo || !ce_hi) { free(ce_lo); free(ce_hi); return PyErr_NoMemory(); }

    for (Py_ssize_t i = 0; i < num_cover; i++) {
        M81 m;
        if (pylong_to_m81(PyList_GET_ITEM(ce_list, i), &m) < 0) {
            free(ce_lo); free(ce_hi);
            return NULL;
        }
        ce_lo[i] = m.lo;
        ce_hi[i] = m.hi;
    }

    M81 base, cand, endo;
    if (pylong_to_m81(base_obj, &base) < 0 ||
        pylong_to_m81(cand_obj, &cand) < 0 ||
        pylong_to_m81(endo_obj, &endo) < 0) {
        free(ce_lo); free(ce_hi);
        return NULL;
    }

    int max_out = 10000;
    FishResult *out = malloc(max_out * sizeof(FishResult));
    if (!out) { free(ce_lo); free(ce_hi); return PyErr_NoMemory(); }

    int nfound = fish_find_covers(
        ce_lo, ce_hi, (int)num_cover, n,
        base.lo, base.hi,
        cand.lo, cand.hi,
        with_fins, max_fins,
        endo.lo, endo.hi,
        out, max_out
    );
    free(ce_lo);
    free(ce_hi);

    int nresults = nfound < max_out ? nfound : max_out;
    PyObject *result_list = PyList_New(nresults);
    if (!result_list) { free(out); return NULL; }

    for (int i = 0; i < nresults; i++) {
        FishResult *r = &out[i];

        PyObject *indices = PyTuple_New(n);
        if (!indices) goto error;
        for (int k = 0; k < n; k++) {
            PyObject *idx = PyLong_FromLong(r->indices[k]);
            if (!idx) { Py_DECREF(indices); goto error; }
            PyTuple_SET_ITEM(indices, k, idx);
        }

        PyObject *cover = m81_to_pylong((M81){r->cover_lo, r->cover_hi});
        PyObject *fins  = m81_to_pylong((M81){r->fins_lo,  r->fins_hi});
        PyObject *elim  = m81_to_pylong((M81){r->elim_lo,  r->elim_hi});
        if (!cover || !fins || !elim) {
            Py_DECREF(indices); Py_XDECREF(cover); Py_XDECREF(fins); Py_XDECREF(elim);
            goto error;
        }

        PyObject *entry = PyTuple_Pack(4, indices, cover, fins, elim);
        Py_DECREF(indices); Py_DECREF(cover); Py_DECREF(fins); Py_DECREF(elim);
        if (!entry) goto error;
        PyList_SET_ITEM(result_list, i, entry);
    }

    free(out);
    return result_list;

error:
    free(out);
    Py_DECREF(result_list);
    return NULL;
}

static PyMethodDef FishAccelMethods[] = {
    {"set_buddies", py_set_buddies, METH_O,
     "set_buddies(buddies) -> None\n"
     "Initialize the 81-cell buddy table from a list of 81 ints (81-bit CellSets)."},
    {"find_covers", py_find_covers, METH_VARARGS,
     "find_covers(ce_masks, n, base_cand, cand_set, with_fins, max_fins, endo_fins)\n"
     "-> list of (indices, cover_mask, fins_mask, elim_mask) tuples"},
    {NULL, NULL, 0, NULL}
};

static PyModuleDef FishAccelModule = {
    PyModuleDef_HEAD_INIT, "_fish_accel", NULL, -1, FishAccelMethods
};

PyMODINIT_FUNC PyInit__fish_accel(void) {
    _py_64 = PyLong_FromLong(64);
    if (!_py_64) return NULL;

    PyObject *one = PyLong_FromLong(1);
    if (!one) return NULL;
    PyObject *shifted = PyNumber_Lshift(one, _py_64);
    Py_DECREF(one);
    if (!shifted) return NULL;
    one = PyLong_FromLong(1);
    if (!one) { Py_DECREF(shifted); return NULL; }
    _py_lo_mask = PyNumber_Subtract(shifted, one);
    Py_DECREF(shifted);
    Py_DECREF(one);
    if (!_py_lo_mask) return NULL;

    return PyModule_Create(&FishAccelModule);
}
