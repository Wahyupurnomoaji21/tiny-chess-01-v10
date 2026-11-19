# Pack v10 engine10.py -> main.py (<=4096 bytes): minify + lzma-alone + base85.
# ASCII base85 so the file is valid UTF-8 (transcript gate).
# Budget hardcoded to 60,000 nodes/move (v2's official config).
import hashlib, lzma, base64
import python_minifier

SRC = '/home/hatch/workspace/makefun/tiny-chess-01-v10/engine10.py'
OUT = '/home/hatch/workspace/makefun/tiny-chess-01-v10/main.py'

src = open(SRC).read()
src = src.replace("BGT = int(os.environ.get('TINYCHESS_NODES', '60000'))", 'BGT = 6e4')
src = src.replace("if __name__ == '__main__':\n    main()", 'main()')
out = python_minifier.minify(src, remove_annotations=True, rename_globals=True)
raw = lzma.compress(out.encode(), format=lzma.FORMAT_ALONE, preset=9 | lzma.PRESET_EXTREME)
assert lzma.decompress(raw, format=lzma.FORMAT_ALONE).decode() == out, 'round-trip failed'
assert lzma.decompress(raw).decode() == out, 'FORMAT_AUTO decode failed'
b85 = base64.b85encode(raw).decode()
assert all(32 <= ord(c) < 127 for c in b85), 'b85 not ASCII printable'
unp = "import lzma as L,base64 as B;exec(L.decompress(B.b85decode('%s')))" % b85
assert len(unp) <= 4096, 'OVER 4096 cap: %d' % len(unp)
open(OUT, 'w').write(unp)
print('src:', len(src), 'minified:', len(out), 'raw:', len(raw), 'b85:', len(b85), 'TOTAL:', len(unp), 'FIT')
print('main.py sha256:', hashlib.sha256(unp.encode()).hexdigest())
