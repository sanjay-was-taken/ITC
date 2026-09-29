import random

def hamming_74_encode_block(bits_4: str) -> str:
    """Encodes 4 data bits into a 7-bit Hamming codeword."""
    if len(bits_4) != 4 or any(bit not in "01" for bit in bits_4):
        raise ValueError("Hamming (7,4) encoding requires exactly 4 binary data bits.")
    d1, d2, d3, d4 = [int(b) for b in bits_4]
    
    # Parity calculations (Even Parity)
    p1 = d1 ^ d2 ^ d4
    p2 = d1 ^ d3 ^ d4
    p3 = d2 ^ d3 ^ d4

    # Structure: [p1, p2, d1, p3, d2, d3, d4]
    return f"{p1}{p2}{d1}{p3}{d2}{d3}{d4}"

def hamming_74_decode_block_detailed(bits_7: str) -> dict:
    """Returns the corrected codeword, syndrome, error position, and data bits."""
    if len(bits_7) != 7 or any(bit not in "01" for bit in bits_7):
        raise ValueError("Hamming (7,4) decoding requires exactly 7 binary bits.")
    b = [int(x) for x in bits_7]

    # Bit positions are 1-based in the specification and 0-based in this list.
    s1 = b[0] ^ b[2] ^ b[4] ^ b[6]
    s2 = b[1] ^ b[2] ^ b[5] ^ b[6]
    s3 = b[3] ^ b[4] ^ b[5] ^ b[6]
    syndrome = s3 * 4 + s2 * 2 + s1
    error_position = syndrome or None

    if error_position is not None:
        b[syndrome - 1] ^= 1

    return {
        "received": bits_7,
        "corrected_codeword": "".join(str(bit) for bit in b),
        "data_bits": f"{b[2]}{b[4]}{b[5]}{b[6]}",
        "syndrome": f"{s3}{s2}{s1}",
        "syndrome_value": syndrome,
        "error_position": error_position,
        "corrected": error_position is not None,
    }

def hamming_74_decode_block(bits_7: str) -> tuple[str, bool]:
    """Decodes a 7-bit word, preserving the original compact return value."""
    result = hamming_74_decode_block_detailed(bits_7)
    return result["data_bits"], result["corrected"]

def channel_encode(bit_stream: str) -> tuple[str, int]:
    """Pads bit stream and encodes into Hamming (7,4) blocks."""
    if any(bit not in "01" for bit in bit_stream):
        raise ValueError("Channel encoding requires a binary input stream.")
    # Pad bitstream to multiple of 4
    padding = (4 - (len(bit_stream) % 4)) % 4
    padded_stream = bit_stream + ("0" * padding)
    
    encoded_blocks = []
    for i in range(0, len(padded_stream), 4):
        block = padded_stream[i:i+4]
        encoded_blocks.append(hamming_74_encode_block(block))

    return "".join(encoded_blocks), padding

def inject_channel_noise(encoded_stream: str, ber_percent: float) -> str:
    """Simulates a noisy channel by flipping bits based on Bit Error Rate (BER %)."""
    bits = list(encoded_stream)
    prob = ber_percent / 100.0
    
    for i in range(len(bits)):
        if random.random() < prob:
            bits[i] = '1' if bits[i] == '0' else '0'
            
    return "".join(bits)

def channel_decode_detailed(noisy_stream: str, padding: int) -> dict:
    """Decodes a channel stream and returns details for every 7-bit block."""
    if any(bit not in "01" for bit in noisy_stream) or len(noisy_stream) % 7:
        raise ValueError("Channel decoding requires a binary stream of complete 7-bit blocks.")
    if not isinstance(padding, int) or not 0 <= padding <= 3:
        raise ValueError("Padding must be an integer from 0 to 3.")

    decoded_blocks = []
    blocks = []
    for i in range(0, len(noisy_stream), 7):
        result = hamming_74_decode_block_detailed(noisy_stream[i:i+7])
        decoded_blocks.append(result["data_bits"])
        blocks.append(result)

    recovered_stream = "".join(decoded_blocks)
    if padding > 0:
        recovered_stream = recovered_stream[:-padding]

    return {
        "blocks": blocks,
        "recovered_bits": recovered_stream,
        "corrected_blocks": sum(block["corrected"] for block in blocks),
    }

def channel_decode(noisy_stream: str, padding: int) -> tuple[str, int]:
    """Preserves the original compact channel-decoder return value."""
    result = channel_decode_detailed(noisy_stream, padding)
    return result["recovered_bits"], result["corrected_blocks"]