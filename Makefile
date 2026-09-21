.PHONY: all setup build-ext build-rust build-daemon clean test

# Default target
all: build-ext build-rust

# 1. Unified Setup: Builds extension and Rust workspace
setup: build-ext build-rust
	@echo "✅ All components built successfully."

# 2. Build the TypeScript Extension
build-ext:
	@echo "📦 Building Chrome Extension..."
	cd apps/extension && npm install && npm run build
	@echo "✅ Extension built in apps/extension/dist"

# 3. Build the Rust Utilities (Release Mode)
build-rust:
	@echo "🦀 Building Rust Workspace (Release Mode)..."
	cargo build --release
	@echo "✅ Rust workspace built successfully."

# Backward compatibility alias
build-daemon: build-rust

# 4. Run all tests (Rust Workspace + Extension Vitest Suite)
test:
	@echo "🧪 Running Rust Workspace Tests..."
	cargo test --workspace
	@echo "🧪 Running Extension Unit Tests..."
	cd apps/extension && npm test

# 5. Clean all artifacts
clean:
	@echo "🧹 Cleaning build artifacts..."
	rm -rf apps/extension/dist
	cargo clean
	@echo "✅ Clean complete."