import unittest
from unittest.mock import patch

from app import simulate
from backend import compress_text, decompress_bits, serialize_huffman_tree
from channel import (
    channel_decode,
    channel_decode_detailed,
    channel_encode,
    hamming_74_decode_block_detailed,
    hamming_74_encode_block,
    inject_channel_noise,
)


class HuffmanTests(unittest.TestCase):
    def test_data_uses_expected_prefix_codes(self):
        bits, codes, tree, original_size = compress_text("DATA")

        self.assertEqual(codes, {"A": "0", "D": "10", "T": "11"})
        self.assertEqual(bits, "100110")
        self.assertEqual(original_size, 32)
        self.assertEqual(decompress_bits(bits, tree), "DATA")
        self.assertIsInstance(serialize_huffman_tree(tree), dict)

    def test_equal_frequencies_have_stable_codebook(self):
        _, first_codes, _, _ = compress_text("DATA")
        _, second_codes, _, _ = compress_text("ATAD")

        self.assertEqual(first_codes, second_codes)


class HammingTests(unittest.TestCase):
    def test_even_parity_example_codewords(self):
        self.assertEqual(hamming_74_encode_block("1001"), "0011001")
        self.assertEqual(hamming_74_encode_block("1000"), "1110000")

    def test_each_single_bit_error_is_identified_and_corrected(self):
        original = hamming_74_encode_block("1001")
        for position in range(7):
            with self.subTest(position=position + 1):
                received = list(original)
                received[position] = "1" if received[position] == "0" else "0"
                decoded = hamming_74_decode_block_detailed("".join(received))

                self.assertEqual(decoded["syndrome_value"], position + 1)
                self.assertEqual(decoded["corrected_codeword"], original)
                self.assertEqual(decoded["data_bits"], "1001")

    def test_clean_codeword_has_zero_syndrome(self):
        decoded = hamming_74_decode_block_detailed("0011001")

        self.assertEqual(decoded["syndrome"], "000")
        self.assertIsNone(decoded["error_position"])
        self.assertFalse(decoded["corrected"])

    def test_ber_flips_each_bit_independently(self):
        with patch("channel.random.random", side_effect=[0.1, 0.9, 0.8, 0.2]):
            received = inject_channel_noise("0101", 50)

        self.assertEqual(received, "1100")

    def test_complete_data_example_and_detailed_correction(self):
        compressed, _, tree, _ = compress_text("DATA")
        transmitted, padding = channel_encode(compressed)
        received = transmitted[:5] + "1" + transmitted[6:]
        decoded = channel_decode_detailed(received, padding)
        recovered, corrected_blocks = channel_decode(received, padding)

        self.assertEqual(transmitted, "00110011110000")
        self.assertEqual(received[:7], "0011011")
        self.assertEqual(decoded["blocks"][0]["syndrome"], "110")
        self.assertEqual(decoded["blocks"][0]["corrected_codeword"], "0011001")
        self.assertEqual(recovered, "100110")
        self.assertEqual(decompress_bits(recovered, tree), "DATA")
        self.assertEqual(corrected_blocks, 1)

    def test_invalid_codeword_is_rejected(self):
        with self.assertRaises(ValueError):
            hamming_74_encode_block("10x1")
        with self.assertRaises(ValueError):
            hamming_74_decode_block_detailed("101")


class PipelineApiTests(unittest.TestCase):
    def test_api_exposes_each_stage_for_the_example(self):
        result = simulate({"text": "DATA", "noise_percent": 0, "forced_error_bit": 6})

        self.assertEqual(result["ascii_bits"], "01000100010000010101010001000001")
        self.assertEqual(result["compressed_bits"], "100110")
        self.assertEqual(result["padded_bits"], "10011000")
        self.assertEqual(result["transmitted_bits"], "00110011110000")
        self.assertEqual(result["blocks"][0]["changed_positions"], [6])
        self.assertEqual(result["blocks"][0]["syndrome"], "110")
        self.assertTrue(result["matches"])
        self.assertEqual(result["reconstructed_text"], "DATA")


if __name__ == "__main__":
    unittest.main()
