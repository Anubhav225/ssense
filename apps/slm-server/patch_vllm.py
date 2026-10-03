import os

FILEPATH = '/usr/local/lib/python3.12/dist-packages/vllm/v1/worker/gpu/buffer_utils.py'

with open(FILEPATH, 'r') as f:
    content = f.read()

# 1. Remove the UVA availability check that raises RuntimeError
content = content.replace(
    'if not is_uva_available():\n            raise RuntimeError("UVA is not available")',
    'if not is_uva_available():\n            pass'
)

# 2. Prevent UvaBuffer from trying to get a hardware UVA view, use a standard GPU tensor instead
content = content.replace(
    'self.uva = get_accelerator_view_from_cpu_tensor(self.cpu)',
    'self.uva = torch.zeros_like(self.cpu, device="cuda")'
)

# 3. Modify UvaBufferPool.copy_to_uva to manually copy the data to the GPU tensor
original_copy = '''    def copy_to_uva(self, x: torch.Tensor | np.ndarray) -> torch.Tensor:
        self.buf = self._uva_bufs[self._idx]
        self._idx = (self._idx + 1) % len(self._uva_bufs)
        self.buf.np[: len(x)] = x
        return self.buf.uva[: len(x)]'''

patched_copy = '''    def copy_to_uva(self, x: torch.Tensor | np.ndarray) -> torch.Tensor:
        self.buf = self._uva_bufs[self._idx]
        self._idx = (self._idx + 1) % len(self._uva_bufs)
        self.buf.np[: len(x)] = x
        self.buf.uva[:len(x)].copy_(self.buf.cpu[:len(x)], non_blocking=True)
        return self.buf.uva[: len(x)]'''

content = content.replace(original_copy, patched_copy)

# 4. Modify states.py to disable uva_instead_of_gpu for StagedWriteTensor (since it allocates 8MB on GPU, it's fine)
STATES_FILEPATH = '/usr/local/lib/python3.12/dist-packages/vllm/v1/worker/gpu/states.py'
with open(STATES_FILEPATH, 'r') as f:
    states_content = f.read()

states_content = states_content.replace('uva_instead_of_gpu=True', 'uva_instead_of_gpu=False')

with open(FILEPATH, 'w') as f:
    f.write(content)

with open(STATES_FILEPATH, 'w') as f:
    f.write(states_content)

print("vLLM UVA patching applied successfully!")
