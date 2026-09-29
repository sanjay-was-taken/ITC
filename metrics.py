import math
from collections import Counter

def calculate_entropy(data: str) -> float:
    """Calculates Shannon Entropy H(X) in bits/symbol."""
    if not data:
        return 0.0
    
    length = len(data)
    counts = Counter(data)
    entropy = 0.0
    
    for char, count in counts.items():
        p = count / length
        entropy -= p * math.log2(p)
        
    return round(entropy, 4)

def calculate_avg_code_length(huffman_codes: dict, text_data: str) -> float:
    """Calculates Average Code Length L = SUM(P_i * L_i)."""
    if not text_data or not huffman_codes:
        return 0.0
    
    length = len(text_data)
    counts = Counter(text_data)
    avg_length = 0.0
    
    for char, count in counts.items():
        p = count / length
        code_length = len(huffman_codes[char])
        avg_length += p * code_length
        
    return round(avg_length, 4)

def calculate_efficiency(entropy: float, avg_code_length: float) -> float:
    """Calculates Coding Efficiency η = H(X) / L * 100%."""
    if avg_code_length == 0:
        return 0.0
    efficiency = (entropy / avg_code_length) * 100
    return round(min(efficiency, 100.0), 2)  # Cap at 100% due to precision rounding

def calculate_ber(original_bits: str, received_bits: str) -> float:
    """Calculates Bit Error Rate (BER) between transmitted and received streams."""
    if not original_bits or not received_bits or len(original_bits) != len(received_bits):
        return 0.0
    
    flipped_bits = sum(1 for b1, b2 in zip(original_bits, received_bits) if b1 != b2)
    ber = (flipped_bits / len(original_bits)) * 100
    return round(ber, 2)