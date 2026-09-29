# Signal Lab

A dependency-free browser demonstration of 8-bit ASCII input, Huffman source coding, information-theory metrics, Hamming (7,4) even-parity error correction, and noisy-channel recovery. The local Python server runs the core algorithm modules and provides the browser with every intermediate stage.

## Run

From this folder, with the project virtual environment active:

```powershell
python app.py
```

Open http://127.0.0.1:8000. To use another port, pass it as the first argument, for example `python app.py 8080`.

The initial `DATA` example injects a deterministic error at transmitted bit 6 so the syndrome and correction are visible. Disable **Teaching fault** to send without that forced error; increase **Bit error rate** to simulate random channel noise. Inputs are limited to 10,000 7-bit ASCII characters.

Select a numbered stage or use **Previous** and **Next** to inspect the ASCII bytes, Huffman tree and codebook, padded source stream, Hamming codewords, noisy bits, syndrome corrections, and reconstructed output. In the Hamming views, data bits are dark, parity bits cyan, channel flips red, and decoder corrections green.

## Verify the core algorithms

With the project virtual environment active, run:

```powershell
python -m unittest discover -v
```
