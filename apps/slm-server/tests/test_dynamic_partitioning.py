import unittest
from unittest.mock import patch, MagicMock
import torch

from engine import (
    compute_dynamic_partition_budgets,
    detect_hardware_capabilities,
    get_system_ram_gb,
    is_unified_memory,
)


class TestDynamicPartitioning(unittest.TestCase):
    def test_compute_dynamic_partition_budgets_rtx3060_12gb(self):
        """12GB GPU should reserve ~2.6GB for KV cache and allocate ~9.4GB for weights."""
        total_vram_gb = 12.0
        total_ram_gb = 32.0
        gpu_budget, cpu_budget, kv_headroom = compute_dynamic_partition_budgets(
            total_vram_gb=total_vram_gb,
            total_ram_gb=total_ram_gb,
            model_weight_gb=15.2,
        )
        # GPU weight budget + KV headroom must sum to total VRAM
        self.assertAlmostEqual(gpu_budget + kv_headroom, total_vram_gb, places=2)
        # Headroom must be at least 2.0GB
        self.assertGreaterEqual(kv_headroom, 2.0)
        # GPU weight budget should be between 8.5GB and 10.0GB
        self.assertGreaterEqual(gpu_budget, 8.5)
        self.assertLessEqual(gpu_budget, 10.0)
        # CPU budget must safely accommodate the remainder (~6GB)
        self.assertGreaterEqual(cpu_budget, 16.0)

    def test_compute_dynamic_partition_budgets_8gb_gpu(self):
        """8GB GPU should reserve ~2.0GB for KV cache and allocate ~6.0GB for weights."""
        total_vram_gb = 8.0
        total_ram_gb = 32.0
        gpu_budget, cpu_budget, kv_headroom = compute_dynamic_partition_budgets(
            total_vram_gb=total_vram_gb,
            total_ram_gb=total_ram_gb,
            model_weight_gb=15.2,
        )
        self.assertAlmostEqual(gpu_budget + kv_headroom, total_vram_gb, places=2)
        self.assertGreaterEqual(kv_headroom, 2.0)
        self.assertGreaterEqual(gpu_budget, 5.0)
        self.assertLessEqual(gpu_budget, 6.5)

    def test_compute_dynamic_partition_budgets_24gb_gpu(self):
        """24GB GPU should cap KV headroom reasonably and allocate ample GPU memory."""
        total_vram_gb = 24.0
        total_ram_gb = 64.0
        gpu_budget, cpu_budget, kv_headroom = compute_dynamic_partition_budgets(
            total_vram_gb=total_vram_gb,
            total_ram_gb=total_ram_gb,
            model_weight_gb=15.2,
        )
        self.assertAlmostEqual(gpu_budget + kv_headroom, total_vram_gb, places=2)
        self.assertLessEqual(kv_headroom, 3.5)
        self.assertGreater(gpu_budget, 20.0)

    @patch("engine.get_gpu_devices")
    @patch("engine.is_unified_memory")
    def test_detect_hardware_capabilities_cpu_only(self, mock_unified, mock_gpus):
        mock_gpus.return_value = []
        mock_unified.return_value = False
        self.assertEqual(detect_hardware_capabilities(), "cpu")

    @patch("engine.get_gpu_devices")
    @patch("engine.is_unified_memory")
    def test_detect_hardware_capabilities_jetson(self, mock_unified, mock_gpus):
        mock_gpus.return_value = [{"index": 0, "name": "Orin", "total_gb": 32.0}]
        mock_unified.return_value = True
        self.assertEqual(detect_hardware_capabilities(), "jetson")

    @patch("engine.get_gpu_devices")
    @patch("engine.is_unified_memory")
    def test_detect_hardware_capabilities_hybrid_rtx3060(self, mock_unified, mock_gpus):
        mock_gpus.return_value = [{"index": 0, "name": "NVIDIA GeForce RTX 3060", "total_gb": 12.0}]
        mock_unified.return_value = False
        self.assertEqual(detect_hardware_capabilities(), "hybrid")

    @patch("engine.get_gpu_devices")
    @patch("engine.is_unified_memory")
    def test_detect_hardware_capabilities_full_gpu(self, mock_unified, mock_gpus):
        mock_gpus.return_value = [{"index": 0, "name": "NVIDIA A100", "total_gb": 40.0}]
        mock_unified.return_value = False
        self.assertEqual(detect_hardware_capabilities(), "gpu")

    def test_get_system_ram_gb_positive(self):
        ram = get_system_ram_gb()
        self.assertGreater(ram, 0.0)


if __name__ == "__main__":
    unittest.main()
