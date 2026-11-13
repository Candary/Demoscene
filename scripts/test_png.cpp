// Standalone test for writePNG function — verifies byte order fix.
// Compile: g++ -std=c++17 -O2 -DTEST_PNG -o test_png test_png.cpp
// Run: ./test_png && python3 -c "from PIL import Image; img = Image.open('/tmp/test_png.png'); print('OK', img.size, img.mode)"

#include <cstdio>
#include <cstring>
#include <cstdlib>

// Inline copy of writePNG function from demo_runtime.cpp (with P1 fix)
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
        int blockLen = rawLen - offset;
        bool last = false;
        if (blockLen > maxBlock) { blockLen = maxBlock; }
        if (offset + blockLen >= rawLen) last = true;
        zlib[zpos++] = last ? 0x01 : 0x00;
        zlib[zpos++] = blockLen & 0xFF;
        zlib[zpos++] = (blockLen >> 8) & 0xFF;
        zlib[zpos++] = (~blockLen) & 0xFF;
        zlib[zpos++] = ((~blockLen) >> 8) & 0xFF;
        memcpy(zlib + zpos, raw + offset, blockLen);
        zpos += blockLen;
        offset += blockLen;
    }
    unsigned int adler = 1;
    for (int i = 0; i < rawLen; i++) {
        adler = (adler + raw[i]) % 65521;
        if (i % 5552 == 5551) adler = (adler + 1) % 65521;
    }
    unsigned int a1 = adler & 0xFFFF;
    unsigned int a2 = (adler >> 16) & 0xFFFF;
    zlib[zpos++] = (a2 >> 8) & 0xFF; zlib[zpos++] = a2 & 0xFF;
    zlib[zpos++] = (a1 >> 8) & 0xFF; zlib[zpos++] = a1 & 0xFF;
    writeChunk("IDAT", zlib, zpos);
    writeChunk("IEND", nullptr, 0);
    delete[] raw;
    delete[] zlib;
    fclose(f);
}

int main() {
    // Test 1x1 red pixel
    unsigned char px[4] = {255, 0, 0, 255};
    writePNG("/tmp/test_png.png", 1, 1, px);
    printf("Wrote /tmp/test_png.png (1x1 red)\n");
    return 0;
}
