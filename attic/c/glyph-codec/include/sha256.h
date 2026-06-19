/*
 * SHA-256 implementation — public domain (originally by Brad Conte, 2012).
 * Single-header form. Include in exactly one .c file with SHA256_IMPLEMENTATION defined.
 */
#ifndef SHA256_H
#define SHA256_H

#include <stddef.h>
#include <stdint.h>

#define SHA256_BLOCK_SIZE 32  /* bytes */

typedef struct {
    uint8_t  data[64];
    uint32_t datalen;
    uint64_t bitlen;
    uint32_t state[8];
} sha256_ctx_t;

void sha256_init(sha256_ctx_t *ctx);
void sha256_update(sha256_ctx_t *ctx, const uint8_t *data, size_t len);
void sha256_final(sha256_ctx_t *ctx, uint8_t hash[SHA256_BLOCK_SIZE]);

#endif /* SHA256_H */
