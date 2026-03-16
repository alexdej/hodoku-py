/*
 * Python C extension: backtracking solver for puzzle generation.
 *
 * Port of generator.py's _solve / _set_cell_valid / _set_all_exposed_singles
 * into C for ~100-1000x speedup over pure Python.
 *
 * 81-bit candidate_sets are split into lo (bits 0-63) and hi (bits 64-80).
 *
 * Exported Python API:
 *   init_tables(buddies, cell_constraints, all_unit_masks)
 *       Initialize static lookup tables from Python data.
 *   solve(values, candidates, candidate_sets, free_counts)
 *       -> (solution_count, solution_list)
 *       Run backtracking solver on the given grid state.
 */

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>

/* ---- Constants ---- */

#define LENGTH 81
#define MAX_STACK 82
#define NUM_CONSTRAINTS 27
#define NUM_DIGITS 10       /* index 0 unused, digits 1-9 */

/* ---- 81-bit mask helpers ---- */

typedef struct { uint64_t lo; uint32_t hi; } M81;

static inline M81 m81_or(M81 a, M81 b)  { return (M81){a.lo | b.lo, a.hi | b.hi}; }
static inline M81 m81_and(M81 a, M81 b) { return (M81){a.lo & b.lo, a.hi & b.hi}; }
static inline M81 m81_clear_bit(M81 m, int bit) {
    if (bit < 64) m.lo &= ~((uint64_t)1 << bit);
    else          m.hi &= ~((uint32_t)1 << (bit - 64));
    return m;
}
static inline M81 m81_set_bit(M81 m, int bit) {
    if (bit < 64) m.lo |= (uint64_t)1 << bit;
    else          m.hi |= (uint32_t)1 << (bit - 64);
    return m;
}
static inline int m81_test_bit(M81 m, int bit) {
    if (bit < 64) return (m.lo >> bit) & 1;
    else          return (m.hi >> (bit - 64)) & 1;
}
static inline int m81_is_zero(M81 m) { return m.lo == 0 && m.hi == 0; }
static inline M81 m81_zero(void) { return (M81){0, 0}; }

/* Return index of lowest set bit, or -1 if zero */
static inline int m81_lsb(M81 m) {
    if (m.lo) return __builtin_ctzll(m.lo);
    if (m.hi) return 64 + __builtin_ctz(m.hi);
    return -1;
}

/* Isolate lowest set bit */
static inline M81 m81_isolate_lsb(M81 m) {
    if (m.lo) return (M81){m.lo & (-(int64_t)m.lo), 0};
    if (m.hi) return (M81){0, m.hi & (-(int32_t)m.hi)};
    return m81_zero();
}

static inline int popcount16(unsigned int x) {
    return __builtin_popcount(x);
}

/* ---- Static tables (initialized from Python) ---- */

static M81 g_buddies[LENGTH];
static int g_cell_constraints[LENGTH][3];  /* 3 constraints per cell */
static M81 g_all_unit_masks[NUM_CONSTRAINTS];
static int g_tables_initialized = 0;

/* DIGIT_MASKS[d] = 1 << (d-1) for d=1..9, DIGIT_MASKS[0] = 0 */
static const uint16_t DIGIT_MASKS[NUM_DIGITS] = {
    0, 1, 2, 4, 8, 16, 32, 64, 128, 256
};

/* POSSIBLE_VALUES[mask] = list of digits present in mask */
static int g_possible_values[512][9];
static int g_possible_values_len[512];

static void init_possible_values(void) {
    for (int mask = 0; mask < 512; mask++) {
        int count = 0;
        for (int d = 1; d <= 9; d++) {
            if (mask & (1 << (d - 1))) {
                g_possible_values[mask][count++] = d;
            }
        }
        g_possible_values_len[mask] = count;
    }
}

/* ---- Grid state for backtracking ---- */

typedef struct {
    int values[LENGTH];
    uint16_t candidates[LENGTH];     /* 9-bit candidate mask per cell */
    M81 candidate_sets[NUM_DIGITS];  /* per-digit 81-bit cell set */
    int free[NUM_CONSTRAINTS][NUM_DIGITS]; /* free[constraint][digit] */

    /* Queues: linear buffers, head/tail indices.
     * Each set_cell_valid can produce up to ~30 queue entries (3 constraints
     * × 9 digits for HS, plus NS).  A full propagation chain can cascade
     * through all 81 cells.  2048 entries is generous. */
    int ns_queue[2048][2];  /* (index, value) pairs */
    int ns_head, ns_tail;
    int hs_queue[2048][2];
    int hs_head, hs_tail;
} GridState;

#define QUEUE_CAP 2048

static inline void ns_clear(GridState *g) { g->ns_head = g->ns_tail = 0; }
static inline void hs_clear(GridState *g) { g->hs_head = g->hs_tail = 0; }
static inline int ns_empty(GridState *g) { return g->ns_head == g->ns_tail; }
static inline int hs_empty(GridState *g) { return g->hs_head == g->hs_tail; }

static inline void ns_push(GridState *g, int index, int value) {
    if (g->ns_tail < QUEUE_CAP) {
        g->ns_queue[g->ns_tail][0] = index;
        g->ns_queue[g->ns_tail][1] = value;
        g->ns_tail++;
    }
}

static inline void hs_push(GridState *g, int index, int value) {
    if (g->hs_tail < QUEUE_CAP) {
        g->hs_queue[g->hs_tail][0] = index;
        g->hs_queue[g->hs_tail][1] = value;
        g->hs_tail++;
    }
}

static inline void ns_pop(GridState *g, int *index, int *value) {
    *index = g->ns_queue[g->ns_head][0];
    *value = g->ns_queue[g->ns_head][1];
    g->ns_head++;
}

static inline void hs_pop(GridState *g, int *index, int *value) {
    *index = g->hs_queue[g->hs_head][0];
    *value = g->hs_queue[g->hs_head][1];
    g->hs_head++;
}

/* ---- Copy grid state ---- */

static void copy_state(GridState *dst, const GridState *src) {
    memcpy(dst->values, src->values, sizeof(dst->values));
    memcpy(dst->candidates, src->candidates, sizeof(dst->candidates));
    memcpy(dst->candidate_sets, src->candidate_sets, sizeof(dst->candidate_sets));
    memcpy(dst->free, src->free, sizeof(dst->free));
    ns_clear(dst);
    hs_clear(dst);
}

/* ---- Constraint propagation ---- */

static int del_cand_valid(GridState *g, int index, int digit) {
    uint16_t mask = DIGIT_MASKS[digit];
    if (!(g->candidates[index] & mask))
        return 1;  /* already absent */

    g->candidates[index] &= ~mask;
    if (g->candidates[index] == 0)
        return 0;  /* cell has no candidates */

    g->candidate_sets[digit] = m81_clear_bit(g->candidate_sets[digit], index);

    for (int ci = 0; ci < 3; ci++) {
        int c = g_cell_constraints[index][ci];
        g->free[c][digit]--;
        if (g->free[c][digit] == 1) {
            M81 rem = m81_and(g->candidate_sets[digit], g_all_unit_masks[c]);
            if (!m81_is_zero(rem)) {
                int cell = m81_lsb(rem);
                hs_push(g, cell, digit);
            }
        }
    }

    uint16_t remaining = g->candidates[index];
    if (remaining != 0 && (remaining & (remaining - 1)) == 0) {
        /* Exactly one candidate left → naked single */
        int d;
        /* bit_length equivalent: find position of the single set bit + 1,
           but we need the digit value which is bit_position + 1.
           For a power of 2, __builtin_ctz gives the bit position. */
        if (remaining) {
            d = __builtin_ctz(remaining) + 1;
            ns_push(g, index, d);
        }
    }

    return 1;
}

static int set_cell_valid(GridState *g, int index, int value) {
    if (g->values[index] == value)
        return 1;

    int valid = 1;
    g->values[index] = value;

    /* Step 1: eliminate value from every buddy */
    M81 buddies = g_buddies[index];
    while (!m81_is_zero(buddies)) {
        int j = m81_lsb(buddies);
        buddies = m81_clear_bit(buddies, j);
        if (!del_cand_valid(g, j, value))
            valid = 0;
    }

    /* Step 2: clear all remaining candidates from this cell */
    uint16_t old_mask = g->candidates[index];
    g->candidates[index] = 0;
    for (int d = 1; d <= 9; d++) {
        if (old_mask & DIGIT_MASKS[d]) {
            g->candidate_sets[d] = m81_clear_bit(g->candidate_sets[d], index);
            for (int ci = 0; ci < 3; ci++) {
                int c = g_cell_constraints[index][ci];
                g->free[c][d]--;
                if (g->free[c][d] == 1 && d != value) {
                    M81 rem = m81_and(g->candidate_sets[d], g_all_unit_masks[c]);
                    if (!m81_is_zero(rem)) {
                        int cell = m81_lsb(rem);
                        hs_push(g, cell, d);
                    }
                } else if (g->free[c][d] == 0 && d != value) {
                    valid = 0;
                }
            }
        }
    }

    return valid;
}

static int set_all_exposed_singles(GridState *g) {
    int valid = 1;

    for (;;) {
        /* First all naked singles */
        while (valid && !ns_empty(g)) {
            int index, value;
            ns_pop(g, &index, &value);
            if (g->candidates[index] & DIGIT_MASKS[value]) {
                valid = set_cell_valid(g, index, value);
            }
        }

        /* Then all hidden singles */
        while (valid && !hs_empty(g)) {
            int index, value;
            hs_pop(g, &index, &value);
            if (g->candidates[index] & DIGIT_MASKS[value]) {
                valid = set_cell_valid(g, index, value);
            }
        }

        if (!valid || (ns_empty(g) && hs_empty(g)))
            break;
    }

    return valid;
}

/* ---- Stack entry for backtracking ---- */

typedef struct {
    int index;
    int candidates[9];
    int num_candidates;
    int cand_index;
} StackEntry;

/* ---- Core solver ---- */

static int solve(GridState *grids, StackEntry *stack, int solution[LENGTH]) {
    int solution_count = 0;

    /* Propagate queued singles from setup */
    if (!set_all_exposed_singles(&grids[0]))
        return 0;

    /* Check if already solved */
    int unsolved = 0;
    for (int i = 0; i < LENGTH; i++) {
        if (grids[0].values[i] == 0) unsolved++;
    }
    if (unsolved == 0) {
        memcpy(solution, grids[0].values, sizeof(int) * LENGTH);
        return 1;
    }

    int level = 0;

    for (;;) {
        /* Count unsolved cells */
        unsolved = 0;
        for (int i = 0; i < LENGTH; i++) {
            if (grids[level].values[i] == 0) unsolved++;
        }

        if (unsolved == 0) {
            /* Found a solution */
            solution_count++;
            if (solution_count == 1) {
                memcpy(solution, grids[level].values, sizeof(int) * LENGTH);
            } else if (solution_count > 1) {
                return solution_count;  /* more than one → done */
            }
        } else {
            /* Find unsolved cell with fewest candidates (MRV) */
            int index = -1;
            int best_count = 9;
            for (int i = 0; i < LENGTH; i++) {
                uint16_t cands = grids[level].candidates[i];
                if (cands != 0) {
                    int cnt = popcount16(cands);
                    if (cnt < best_count) {
                        best_count = cnt;
                        index = i;
                    }
                }
            }

            level++;
            if (index < 0) {
                /* No candidates anywhere → invalid */
                return 0;
            }

            stack[level].index = index;
            uint16_t cmask = grids[level - 1].candidates[index];
            int nc = g_possible_values_len[cmask];
            memcpy(stack[level].candidates, g_possible_values[cmask], nc * sizeof(int));
            stack[level].num_candidates = nc;
            stack[level].cand_index = 0;
        }

        /* Try candidates at this level */
        int done = 0;
        for (;;) {
            /* Fall back through levels with no remaining candidates */
            while (stack[level].cand_index >= stack[level].num_candidates) {
                level--;
                if (level <= 0) {
                    done = 1;
                    break;
                }
            }
            if (done)
                break;

            /* Try next candidate */
            int next_cand = stack[level].candidates[stack[level].cand_index];
            stack[level].cand_index++;

            /* Copy parent state */
            copy_state(&grids[level], &grids[level - 1]);

            if (!set_cell_valid(&grids[level], stack[level].index, next_cand))
                continue;  /* invalid → try next */

            if (set_all_exposed_singles(&grids[level]))
                break;  /* valid move → advance to next level */
        }

        if (done)
            break;
    }

    return solution_count;
}

/* ---- Grid initialization (mirrors Grid.__init__) ---- */

static void grid_init(GridState *g) {
    memset(g->values, 0, sizeof(g->values));
    /* All candidates = 0x1FF (all 9 digits) */
    for (int i = 0; i < LENGTH; i++)
        g->candidates[i] = 0x1FF;
    /* candidate_sets[0] = 0, candidate_sets[1..9] = all 81 bits set */
    g->candidate_sets[0] = m81_zero();
    for (int d = 1; d <= 9; d++) {
        g->candidate_sets[d].lo = ~(uint64_t)0;
        g->candidate_sets[d].hi = 0x1FFFF;  /* bits 64-80 */
    }
    /* free[c][0] = 0, free[c][1..9] = cells_in_unit (always 9) */
    for (int c = 0; c < NUM_CONSTRAINTS; c++) {
        g->free[c][0] = 0;
        for (int d = 1; d <= 9; d++)
            g->free[c][d] = 9;
    }
    ns_clear(g);
    hs_clear(g);
}

/* Set a cell value during puzzle setup (mirrors Grid.set_cell) */
static int grid_set_cell(GridState *g, int index, int value) {
    return set_cell_valid(g, index, value);
}

/* Full solve-from-string: init grid, set clues, backtrack */
static int solve_from_string(const char *puzzle, int len,
                             GridState *grids, StackEntry *stack,
                             int solution[LENGTH]) {
    grid_init(&grids[0]);

    for (int i = 0; i < len && i < LENGTH; i++) {
        int v = puzzle[i] - '0';
        if (v >= 1 && v <= 9) {
            grid_set_cell(&grids[0], i, v);
            if (!set_all_exposed_singles(&grids[0]))
                return 0;  /* invalid puzzle */
        }
    }

    return solve(grids, stack, solution);
}

/* Full solve-from-values: init grid, bulk set, rebuild, backtrack */
static int solve_from_values(const int *cell_values,
                             GridState *grids, StackEntry *stack,
                             int solution[LENGTH]) {
    grid_init(&grids[0]);
    GridState *g0 = &grids[0];

    /* Bulk set: place values directly, strip candidates from buddies */
    for (int i = 0; i < LENGTH; i++) {
        int v = cell_values[i];
        if (v >= 1 && v <= 9) {
            g0->values[i] = v;
            g0->candidates[i] = 0;
            M81 buddies = g_buddies[i];
            while (!m81_is_zero(buddies)) {
                int j = m81_lsb(buddies);
                buddies = m81_clear_bit(buddies, j);
                g0->candidates[j] &= ~DIGIT_MASKS[v];
            }
        }
    }

    /* Rebuild free counts, candidate_sets, and queues */
    for (int c = 0; c < NUM_CONSTRAINTS; c++)
        for (int d = 0; d < NUM_DIGITS; d++)
            g0->free[c][d] = 0;

    for (int d = 0; d < NUM_DIGITS; d++)
        g0->candidate_sets[d] = m81_zero();

    ns_clear(g0);
    hs_clear(g0);

    for (int i = 0; i < LENGTH; i++) {
        uint16_t cands = g0->candidates[i];
        if (cands == 0) continue;
        for (int d = 1; d <= 9; d++) {
            if (cands & DIGIT_MASKS[d]) {
                g0->candidate_sets[d] = m81_set_bit(g0->candidate_sets[d], i);
                for (int ci = 0; ci < 3; ci++) {
                    int c = g_cell_constraints[i][ci];
                    g0->free[c][d]++;
                }
            }
        }
    }

    /* Enqueue naked singles */
    for (int i = 0; i < LENGTH; i++) {
        uint16_t cands = g0->candidates[i];
        if (cands != 0 && (cands & (cands - 1)) == 0) {
            ns_push(g0, i, __builtin_ctz(cands) + 1);
        }
    }

    /* Enqueue hidden singles */
    for (int c = 0; c < NUM_CONSTRAINTS; c++) {
        for (int d = 1; d <= 9; d++) {
            if (g0->free[c][d] == 1) {
                M81 rem = m81_and(g0->candidate_sets[d], g_all_unit_masks[c]);
                if (!m81_is_zero(rem)) {
                    int cell = m81_lsb(rem);
                    hs_push(g0, cell, d);
                }
            }
        }
    }

    if (!set_all_exposed_singles(g0))
        return 0;

    return solve(grids, stack, solution);
}

/* ---- Python interface ---- */

static PyObject *_py_lo_mask = NULL;  /* (1 << 64) - 1 */
static PyObject *_py_64 = NULL;

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
    out->hi = (uint32_t)(hi & 0x1FFFF);  /* 17 bits for cells 64-80 */
    return 0;
}

/*
 * init_tables(buddies: list[int], cell_constraints: list[tuple[int,int,int]],
 *             all_unit_masks: list[int]) -> None
 */
static PyObject *py_init_tables(PyObject *self, PyObject *args) {
    PyObject *buddies_list, *constraints_list, *masks_list;

    if (!PyArg_ParseTuple(args, "O!O!O!",
            &PyList_Type, &buddies_list,
            &PyList_Type, &constraints_list,
            &PyList_Type, &masks_list))
        return NULL;

    if (PyList_GET_SIZE(buddies_list) != LENGTH) {
        PyErr_SetString(PyExc_ValueError, "buddies must have 81 elements");
        return NULL;
    }
    if (PyList_GET_SIZE(constraints_list) != LENGTH) {
        PyErr_SetString(PyExc_ValueError, "cell_constraints must have 81 elements");
        return NULL;
    }
    if (PyList_GET_SIZE(masks_list) != NUM_CONSTRAINTS) {
        PyErr_SetString(PyExc_ValueError, "all_unit_masks must have 27 elements");
        return NULL;
    }

    for (int i = 0; i < LENGTH; i++) {
        if (pylong_to_m81(PyList_GET_ITEM(buddies_list, i), &g_buddies[i]) < 0)
            return NULL;
    }

    for (int i = 0; i < LENGTH; i++) {
        PyObject *tup = PyList_GET_ITEM(constraints_list, i);
        if (!PyTuple_Check(tup) || PyTuple_GET_SIZE(tup) != 3) {
            PyErr_SetString(PyExc_ValueError, "each constraint must be a 3-tuple");
            return NULL;
        }
        for (int j = 0; j < 3; j++) {
            g_cell_constraints[i][j] = (int)PyLong_AsLong(PyTuple_GET_ITEM(tup, j));
        }
    }

    for (int i = 0; i < NUM_CONSTRAINTS; i++) {
        if (pylong_to_m81(PyList_GET_ITEM(masks_list, i), &g_all_unit_masks[i]) < 0)
            return NULL;
    }

    init_possible_values();
    g_tables_initialized = 1;
    Py_RETURN_NONE;
}

/*
 * solve(values: list[int], candidates: list[int],
 *        candidate_sets: list[int], free_counts: list[list[int]])
 *    -> (solution_count: int, solution: list[int])
 *
 * values: 81 ints (0 for unsolved)
 * candidates: 81 ints (9-bit masks)
 * candidate_sets: 10 Python ints (81-bit masks, index 0 unused)
 * free_counts: 27 lists of 10 ints each
 *
 * The ns_queue and hs_queue from Grid are NOT passed — the caller must
 * drain them (via _set_all_exposed_singles in Python) before calling,
 * OR pass the grid state after set_cell + propagation so queues are empty.
 * Actually, we'll also accept queue data for full fidelity.
 */
static PyObject *py_solve(PyObject *self, PyObject *args) {
    PyObject *values_list, *candidates_list, *cand_sets_list, *free_list;
    PyObject *ns_queue_list = NULL, *hs_queue_list = NULL;

    if (!PyArg_ParseTuple(args, "O!O!O!O!|O!O!",
            &PyList_Type, &values_list,
            &PyList_Type, &candidates_list,
            &PyList_Type, &cand_sets_list,
            &PyList_Type, &free_list,
            &PyList_Type, &ns_queue_list,
            &PyList_Type, &hs_queue_list))
        return NULL;

    if (!g_tables_initialized) {
        PyErr_SetString(PyExc_RuntimeError, "call init_tables() first");
        return NULL;
    }

    if (PyList_GET_SIZE(values_list) != LENGTH ||
        PyList_GET_SIZE(candidates_list) != LENGTH ||
        PyList_GET_SIZE(cand_sets_list) != NUM_DIGITS ||
        PyList_GET_SIZE(free_list) != NUM_CONSTRAINTS) {
        PyErr_SetString(PyExc_ValueError, "wrong array sizes");
        return NULL;
    }

    /* Allocate grid states on heap (too large for stack) */
    GridState *grids = (GridState *)calloc(MAX_STACK, sizeof(GridState));
    StackEntry *stack = (StackEntry *)calloc(MAX_STACK, sizeof(StackEntry));
    if (!grids || !stack) {
        free(grids);
        free(stack);
        return PyErr_NoMemory();
    }

    /* Populate grids[0] from Python data */
    GridState *g0 = &grids[0];
    for (int i = 0; i < LENGTH; i++) {
        g0->values[i] = (int)PyLong_AsLong(PyList_GET_ITEM(values_list, i));
        g0->candidates[i] = (uint16_t)PyLong_AsLong(PyList_GET_ITEM(candidates_list, i));
    }
    for (int d = 0; d < NUM_DIGITS; d++) {
        if (pylong_to_m81(PyList_GET_ITEM(cand_sets_list, d), &g0->candidate_sets[d]) < 0) {
            free(grids); free(stack);
            return NULL;
        }
    }
    for (int c = 0; c < NUM_CONSTRAINTS; c++) {
        PyObject *row = PyList_GET_ITEM(free_list, c);
        if (!PyList_Check(row) || PyList_GET_SIZE(row) != NUM_DIGITS) {
            free(grids); free(stack);
            PyErr_SetString(PyExc_ValueError, "free_counts rows must have 10 elements");
            return NULL;
        }
        for (int d = 0; d < NUM_DIGITS; d++) {
            g0->free[c][d] = (int)PyLong_AsLong(PyList_GET_ITEM(row, d));
        }
    }

    /* Load queues if provided */
    ns_clear(g0);
    hs_clear(g0);
    if (ns_queue_list) {
        Py_ssize_t n = PyList_GET_SIZE(ns_queue_list);
        for (Py_ssize_t i = 0; i < n; i++) {
            PyObject *pair = PyList_GET_ITEM(ns_queue_list, i);
            int idx = (int)PyLong_AsLong(PyTuple_GET_ITEM(pair, 0));
            int val = (int)PyLong_AsLong(PyTuple_GET_ITEM(pair, 1));
            ns_push(g0, idx, val);
        }
    }
    if (hs_queue_list) {
        Py_ssize_t n = PyList_GET_SIZE(hs_queue_list);
        for (Py_ssize_t i = 0; i < n; i++) {
            PyObject *pair = PyList_GET_ITEM(hs_queue_list, i);
            int idx = (int)PyLong_AsLong(PyTuple_GET_ITEM(pair, 0));
            int val = (int)PyLong_AsLong(PyTuple_GET_ITEM(pair, 1));
            hs_push(g0, idx, val);
        }
    }

    if (PyErr_Occurred()) {
        free(grids); free(stack);
        return NULL;
    }

    /* Solve */
    int solution[LENGTH];
    memset(solution, 0, sizeof(solution));
    int sol_count = solve(grids, stack, solution);

    free(grids);
    free(stack);

    /* Build result */
    PyObject *sol_list = PyList_New(LENGTH);
    if (!sol_list) return NULL;
    for (int i = 0; i < LENGTH; i++) {
        PyObject *v = PyLong_FromLong(solution[i]);
        if (!v) { Py_DECREF(sol_list); return NULL; }
        PyList_SET_ITEM(sol_list, i, v);
    }

    return Py_BuildValue("(iN)", sol_count, sol_list);
}

/*
 * solve_string(puzzle: str) -> (solution_count: int, solution: list[int])
 * Full solve from an 81-character string.
 */
static PyObject *py_solve_string(PyObject *self, PyObject *arg) {
    if (!g_tables_initialized) {
        PyErr_SetString(PyExc_RuntimeError, "call init_tables() first");
        return NULL;
    }
    if (!PyUnicode_Check(arg)) {
        PyErr_SetString(PyExc_TypeError, "expected str");
        return NULL;
    }

    Py_ssize_t len;
    const char *puzzle = PyUnicode_AsUTF8AndSize(arg, &len);
    if (!puzzle) return NULL;

    GridState *grids = (GridState *)calloc(MAX_STACK, sizeof(GridState));
    StackEntry *stack = (StackEntry *)calloc(MAX_STACK, sizeof(StackEntry));
    if (!grids || !stack) {
        free(grids); free(stack);
        return PyErr_NoMemory();
    }

    int solution[LENGTH];
    memset(solution, 0, sizeof(solution));
    int sol_count = solve_from_string(puzzle, (int)len, grids, stack, solution);

    free(grids);
    free(stack);

    PyObject *sol_list = PyList_New(LENGTH);
    if (!sol_list) return NULL;
    for (int i = 0; i < LENGTH; i++) {
        PyObject *v = PyLong_FromLong(solution[i]);
        if (!v) { Py_DECREF(sol_list); return NULL; }
        PyList_SET_ITEM(sol_list, i, v);
    }

    return Py_BuildValue("(iN)", sol_count, sol_list);
}

/*
 * solve_values(values: list[int]) -> (solution_count: int, solution: list[int])
 * Full solve from an 81-element int list.
 */
static PyObject *py_solve_values(PyObject *self, PyObject *arg) {
    if (!g_tables_initialized) {
        PyErr_SetString(PyExc_RuntimeError, "call init_tables() first");
        return NULL;
    }
    if (!PyList_Check(arg) || PyList_GET_SIZE(arg) != LENGTH) {
        PyErr_SetString(PyExc_ValueError, "expected list of 81 ints");
        return NULL;
    }

    int cell_values[LENGTH];
    for (int i = 0; i < LENGTH; i++) {
        cell_values[i] = (int)PyLong_AsLong(PyList_GET_ITEM(arg, i));
    }
    if (PyErr_Occurred()) return NULL;

    GridState *grids = (GridState *)calloc(MAX_STACK, sizeof(GridState));
    StackEntry *stack = (StackEntry *)calloc(MAX_STACK, sizeof(StackEntry));
    if (!grids || !stack) {
        free(grids); free(stack);
        return PyErr_NoMemory();
    }

    int solution[LENGTH];
    memset(solution, 0, sizeof(solution));
    int sol_count = solve_from_values(cell_values, grids, stack, solution);

    free(grids);
    free(stack);

    PyObject *sol_list = PyList_New(LENGTH);
    if (!sol_list) return NULL;
    for (int i = 0; i < LENGTH; i++) {
        PyObject *v = PyLong_FromLong(solution[i]);
        if (!v) { Py_DECREF(sol_list); return NULL; }
        PyList_SET_ITEM(sol_list, i, v);
    }

    return Py_BuildValue("(iN)", sol_count, sol_list);
}

/* ---- Module definition ---- */

static PyMethodDef GenAccelMethods[] = {
    {"init_tables", py_init_tables, METH_VARARGS,
     "init_tables(buddies, cell_constraints, all_unit_masks)\n"
     "Initialize static lookup tables from Python data."},
    {"solve", py_solve, METH_VARARGS,
     "solve(values, candidates, candidate_sets, free_counts "
     "[, ns_queue, hs_queue])\n"
     "-> (solution_count, solution_list)\n"
     "Run backtracking solver on pre-propagated grid state."},
    {"solve_string", py_solve_string, METH_O,
     "solve_string(puzzle: str) -> (solution_count, solution_list)\n"
     "Full solve from an 81-character puzzle string."},
    {"solve_values", py_solve_values, METH_O,
     "solve_values(values: list[int]) -> (solution_count, solution_list)\n"
     "Full solve from an 81-element int list."},
    {NULL, NULL, 0, NULL}
};

static PyModuleDef GenAccelModule = {
    PyModuleDef_HEAD_INIT, "_gen_accel", NULL, -1, GenAccelMethods
};

PyMODINIT_FUNC PyInit__gen_accel(void) {
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

    return PyModule_Create(&GenAccelModule);
}
