import heapq
import json
from collections import Counter

class HuffmanNode:
    def __init__(self, char=None, freq=0):
        self.char = char
        self.freq = freq
        self.left = None
        self.right = None

    def __lt__(self, other):
        return self.freq < other.freq

def build_huffman_tree(text: str):
    """Builds Huffman Tree and returns root node along with frequency dictionary."""
    if not text:
        return None, {}
    
    frequencies = Counter(text)
    heap = []
    for order, (char, freq) in enumerate(sorted(frequencies.items())):
        heap.append((freq, order, HuffmanNode(char, freq)))
    heapq.heapify(heap)

    # Edge case: only one unique character
    if len(heap) == 1:
        root = HuffmanNode(freq=heap[0].freq)
        root.left = heap[0]
        return root, frequencies

    while len(heap) > 1:
        left = heapq.heappop(heap)[2]
        right = heapq.heappop(heap)[2]
        
        merged = HuffmanNode(freq=left.freq + right.freq)
        merged.left = left
        merged.right = right
        heapq.heappush(heap, (merged.freq, order + 1, merged))
        order += 1

    return heap[0][2], frequencies

def serialize_huffman_tree(root):
    """Returns a JSON-serializable representation of a Huffman tree."""
    if root is None:
        return None
    if root.char is not None:
        return {"character": root.char, "frequency": root.freq}
    return {
        "frequency": root.freq,
        "left": serialize_huffman_tree(root.left),
        "right": serialize_huffman_tree(root.right),
    }

def generate_huffman_codes(root, current_code="", codes=None):
    """Recursively generates binary codes from Huffman tree."""
    if codes is None:
        codes = {}

    if root is None:
        return codes

    if root.char is not None:
        codes[root.char] = current_code if current_code != "" else "0"
        return codes

    generate_huffman_codes(root.left, current_code + "0", codes)
    generate_huffman_codes(root.right, current_code + "1", codes)
    return codes

def compress_text(text: str):
    """Compresses text to binary string and returns metadata + codes."""
    if not text:
        return "", {}, None, 0

    root, freqs = build_huffman_tree(text)
    codes = generate_huffman_codes(root)
    
    encoded_bits = "".join(codes[char] for char in text)
    return encoded_bits, codes, root, len(text) * 8  # Original size in bits

def decompress_bits(encoded_bits: str, root) -> str:
    """Decompresses bit stream back to original text using the Huffman Tree."""
    if not encoded_bits or not root:
        return ""

    # Special case: single unique character in file
    if root.char is not None:
        return root.char * len(encoded_bits)
    if root.left and root.left.char is not None and not root.right:
        return root.left.char * len(encoded_bits)

    decoded_text = []
    current_node = root

    for bit in encoded_bits:
        if bit == '0':
            current_node = current_node.left
        elif bit == '1':
            current_node = current_node.right

        if current_node and current_node.char is not None:
            decoded_text.append(current_node.char)
            current_node = root

    return "".join(decoded_text)