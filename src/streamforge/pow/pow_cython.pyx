# pow_cython.pyx
# cython: boundscheck=False
# cython: wraparound=False
# cython: cdivision=True
# cython: initializedcheck=False
# cython: nonecheck=False
# cython: language_level=3

from libc.stdint cimport uint8_t, uint32_t, uint64_t
from libc.stdlib cimport malloc, free
from libc.string cimport memcpy


# ---------- helpers ----------

cdef inline uint32_t rotl32(uint32_t x, int n) noexcept nogil:
    # matches Python re_func: ((x << n) | (x >> (32 - n))) & 0xFFFFFFFF
    return (x << n) | (x >> (32 - n))


cdef inline void ye(uint32_t* s) noexcept nogil:
    # in-place quarter-round over s[0..3]
    cdef uint32_t a0 = s[0], a1 = s[1], a2 = s[2], a3 = s[3]
    a0 = a0 + a1
    a3 = rotl32(a3 ^ a0, 16)
    a2 = a2 + a3
    a1 = rotl32(a1 ^ a2, 12)
    a0 = a0 + a1
    a3 = rotl32(a3 ^ a0, 8)
    a2 = a2 + a3
    a1 = rotl32(a1 ^ a2, 7)
    s[0] = a0; s[1] = a1; s[2] = a2; s[3] = a3


cdef void gr_c(const uint8_t* data, Py_ssize_t data_len, uint32_t* out) noexcept nogil:
    cdef uint32_t st[4]
    st[0] = 1779033703
    st[1] = 3144134277
    st[2] = 1013904242
    st[3] = 2773480762

    cdef uint32_t lr = 2654435761
    cdef uint32_t hr = 2246822519

    cdef Py_ssize_t i
    cdef int rd, s, j, k
    cdef uint32_t b, idx, c, sv, d, nxt

    # ---- process each input byte ----
    for i in range(data_len):
        b = data[i]
        st[0] = st[0] + b
        st[0] = rotl32(st[0], 7)
        ye(st)

    # ---- 8 extra rounds ----
    for i in range(8):
        ye(st)

    # ---- build r[512] ----
    cdef uint32_t r[512]
    for i in range(512):
        ye(st)
        r[i] = st[0] ^ st[2]

    # ---- main mixing loop (dr = 2, be = 512) ----
    for rd in range(2):
        for s in range(512):
            idx = r[s] & 511
            c   = r[s] + r[idx]
            c   = rotl32(c, 13)
            nxt = r[(s + 1) & 511]
            c   = c ^ (nxt * lr)
            r[s] = c
            st[0] = st[0] ^ c
            ye(st)

    # ---- final 8 integers ----
    for j in range(8):
        ye(st)
        sv = st[0]
        # o = 512 // 8 = 64
        for k in range(64):
            d = r[j * 64 + k]
            sv = sv + d
            sv = rotl32(sv, 5)
            sv = sv ^ (d * hr)
        out[j] = sv ^ st[2]


# ---------- Python-facing API ----------

def gr(bytes t):
    """Hash bytes -> list[int] of 8 uint32 words."""
    cdef Py_ssize_t n = len(t)
    cdef uint32_t out[8]
    cdef int i
    gr_c(<const uint8_t*>t, n, out)
    return [out[i] for i in range(8)]


cdef inline int write_u64(uint8_t* buf, uint64_t v) noexcept nogil:
    """Write decimal digits of v into buf; return length."""
    cdef uint8_t tmp[20]
    cdef int n = 0, i
    if v == 0:
        buf[0] = 0x30
        return 1
    while v > 0:
        tmp[n] = <uint8_t>(0x30 + (v % 10))
        v //= 10
        n += 1
    for i in range(n):
        buf[i] = tmp[n - 1 - i]
    return n


def er(str t, int e, double r=180.0):
    """Find nonce s such that gr(t + ':' + str(s))[0] >> 16 == 0."""
    if e <= 0:
        return '0'

    cdef bytes prefix = (t + ':').encode('ascii')
    cdef Py_ssize_t plen = len(prefix)
    cdef Py_ssize_t bufsize = plen + 24          # max uint64 digits = 20
    cdef uint8_t* buf = <uint8_t*>malloc(bufsize)
    if buf == NULL:
        raise MemoryError()

    cdef uint64_t s = 0
    cdef int nlen
    cdef uint32_t out[8]

    try:
        memcpy(buf, <const uint8_t*>prefix, plen)
        while True:
            nlen = write_u64(buf + plen, s)
            gr_c(buf, plen + nlen, out)
            if (out[0] >> 16) == 0:
                return str(s)
            s += 1
    finally:
        free(buf)


def wr(list t):
    """Count leading-zero bits across a list of uint32 words."""
    cdef int e = 0
    cdef uint32_t n
    for n in t:
        if n == 0:
            e += 32
            continue
        return e + (32 - (<int>n).bit_length())
    return e