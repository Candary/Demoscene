// Test writePNG using the EXACT code from demo_runtime.cpp (after P1.1 fix).
// Compiles standalone, writes a 1x1 red PNG, verifies with Pillow.
//
// Compile: g++ -std=c++17 -O2 -o test_png /home/z/my-project/scripts/test_png_v2.cpp
// Run: ./test_png && python3 verify

#include <cstdio>
#include <cstring>
#include <cstdlib>

// === Exact copy of writePNG from demo_runtime.cpp (after P1.1 fix) ===
static void writePNG(const char* filename, int w, int h, const unsigned char* rgba) {
    FILE* f = fopen(filename, "wb");
    if (!f) return;
    static const unsigned char sig[] = {137,80,78,71,13,10,26,10};
    fwrite(sig, 1, 8, f);
    unsigned char ihdr[13] = {0};
    ihdr[0] = (w >> 24) & 0xFF; ihdr[1] = (w >> 16) & 0xFF;
    ihdr[2] = (w >> 8) & 0xFF; ihdr[3] = w & 0xFF;
    ihdr[4] = (h >> 24) & 0xFF; ihdr[5] = (h >> 16) & 0xFF;
    ihdr[6] = (h >> 8) & 0xFF; ihdr[7] = h & 0xFF;
    ihdr[8] = 8;  // bit depth
    ihdr[9] = 6;  // color type: RGBA

    auto writeBE32 = [&](unsigned int v) {
        unsigned char buf[4] = {
            (unsigned char)((v >> 24) & 0xFF),
            (unsigned char)((v >> 16) & 0xFF),
            (unsigned char)((v >> 8) & 0xFF),
            (unsigned char)(v & 0xFF)
        };
        fwrite(buf, 1, 4, f);
    };

    auto writeChunk = [&](const char* type, const unsigned char* data, int len) {
        writeBE32((unsigned int)len);
        fwrite(type, 1, 4, f);
        fwrite(data, 1, len, f);
        static unsigned int table[256];
        static bool init = false;
        if (!init) {
            for (unsigned int i = 0; i < 256; i++) {
                unsigned int c = i;
                for (int k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320 ^ (c >> 1)) : (c >> 1);
                table[i] = c;
            }
            init = true;
        }
        unsigned int crc = 0xFFFFFFFF;
        for (int i = 0; i < 4 + len; i++) {
            unsigned char b = (i < 4) ? type[i] : data[i - 4];
            crc = table[(crc ^ b) & 0xFF] ^ (crc >> 8);
        }
        crc ^= 0xFFFFFFFF;
        writeBE32(crc);
    };
    writeChunk("IHDR", ihdr, 13);
    int rowBytes = w * 4;
    int rawLen = (rowBytes + 1) * h;
    unsigned char* raw = new unsigned char[rawLen];
    for (int y = 0; y < h; y++) {
        raw[y * (rowBytes + 1)] = 0;
        memcpy(raw + y * (rowBytes + 1) + 1, rgba + (h - 1 - y) * rowBytes, rowBytes);
    }
    int maxBlock = 65535;
    int numBlocks = (rawLen + maxBlock - 1) / maxBlock;
    int zlibLen = 2 + numBlocks * 5 + rawLen + 4;
    unsigned char* zlib = new unsigned char[zlibLen];
    int zpos = 0;
    zlib[zpos++] = 0x78; zlib[zpos++] = 0x01;
    int offset = 0;
    while (offset < rawLen) {
        int blockLen = (rawLen - offset < maxBlock) ? (rawLen - offset) : maxBlock;
        bool last = (offset + blockLen >= rawLen);
        zlib[zpos++] = last ? 0x01 : 0x00;
        zlib[zpos++] = blockLen & 0xFF; zlib[zpos++] = (blockLen >> 8) & 0xFF;
        int inv = ~blockLen;
        zlib[zpos++] = inv & 0xFF; zlib[zpos++] = (inv >> 8) & 0xFF;
        memcpy(zlib + zpos, raw + offset, blockLen);
        zpos += blockLen;
        offset += blockLen;
    }
    // Adler32 (correct: both A and B)
    unsigned int a = 1, b = 0;
    for (int i = 0; i < rawLen; i++) { a = (a + raw[i]) % 65521; b = (b + a) % 65521; }
    unsigned int adler = (b << 16) | a;
    zlib[zpos++] = (adler >> 24) & 0xFF; zlib[zpos++] = (adler >> 16) & 0xFF;
    zlib[zpos++] = (adler >> 8) & 0xFF; zlib[zpos++] = adler & 0xFF;
    writeChunk("IDAT", zlib, zpos);
    writeChunk("IEND", nullptr, 0);
    fclose(f);
    delete[] raw;
    delete[] zlib;
}

int main() {
    // Test 1: 1x1 red pixel
    unsigned char px1[4] = {255, 0, 0, 255};
    writePNG("/tmp/test_png_1x1.png", 1, 1, px1);
    printf("Wrote /tmp/test_png_1x1.png (1x1 red)\n");

    // Test 2: 4x4 multi-color
    unsigned char px4[4*4*4];
    for (int y = 0; y < 4; y++) for (int x = 0; x < 4; x++) {
        int i = (y*4 + x) * 4;
        px4[i+0] = x * 64; px4[i+1] = y * 64; px4[i+2] = 128; px4[i+3] = 255;
    }
    writePNG("/tmp/test_png_4x4.png", 4, 4, px4);
    printf("Wrote /tmp/test_png_4x4.png (4x4 gradient)\n");

    return 0;
}
