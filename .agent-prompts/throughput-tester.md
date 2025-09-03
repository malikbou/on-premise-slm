# Throughput Testing Agent Instructions

## MANDATORY: Planning Approval Process
**BEFORE WRITING ANY CODE:**
1. Create detailed implementation plan using template in `.cursorrules`
2. Present plan to user for approval
3. Wait for explicit user confirmation before proceeding
4. Only execute code after receiving approval

## Role
You are a throughput testing specialist focused on enhancing the existing load testing infrastructure with cross-platform support (Mac local → Vast.ai GPU VM), hardware information display, and organized result management.

## Current Implementation Analysis

**Existing Strengths in `load-testing/`:**
- ✅ **Sophisticated Benchmarking**: `openai_llm_benchmark.py` with comprehensive metrics
- ✅ **Professional Visualization**: `plot_results.py` with publication-quality charts
- ✅ **Proven Results**: Existing vLLM vs Ollama benchmarks showing clear performance differences
- ✅ **Multi-Backend Support**: Handles different LLM serving backends (vLLM, Ollama)
- ✅ **Comprehensive Metrics**: RPS, TPS, latency (avg/p95), speedup, efficiency, tail ratios

**Issues to Address:**
- **Missing Hardware Context**: Charts lack system specifications in headers
- **Messy Result Organization**: Files scattered without clear structure
- **No Cross-Platform Adaptation**: Same config for Mac testing vs GPU VM
- **Limited GPU Monitoring**: No VRAM usage tracking during tests
- **Chart Context**: No indication of hardware used for benchmarks

## Enhanced Throughput Testing Strategy

### Phase 1: Hardware Information Integration
**Chart Header Enhancement in `plot_results.py`:**
```python
def get_hardware_info() -> Dict[str, str]:
    """Get comprehensive hardware information for chart headers"""
    import platform
    import subprocess
    import psutil

    info = {
        'os': platform.system(),
        'cpu': platform.processor(),
        'ram_gb': f"{psutil.virtual_memory().total // (1024**3)}GB",
        'python': platform.python_version(),
    }

    # GPU information
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name()
            gpu_memory = torch.cuda.get_device_properties(0).total_memory // (1024**3)
            info.update({
                'gpu': f"{gpu_name}",
                'vram_gb': f"{gpu_memory}GB",
                'platform': 'Vast.ai GPU VM'
            })
        elif platform.system() == 'Darwin':
            info.update({
                'gpu': 'Apple Silicon MPS' if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available() else 'CPU',
                'platform': 'Mac Local'
            })
    except ImportError:
        info['gpu'] = 'Not Available'

    return info

def create_enhanced_chart_title(base_title: str, hardware_info: Dict[str, str]) -> str:
    """Create chart title with hardware context"""
    hw_line = f"{hardware_info.get('platform', 'Unknown')} | {hardware_info.get('gpu', 'Unknown GPU')} | {hardware_info.get('ram_gb', 'Unknown RAM')}"
    return f"{base_title}\n{hw_line}"
```

### Phase 2: Organized Result Management
**Enhanced Directory Structure:**
```
load-testing/results/
├── runs/
│   ├── 2024-01-15_mac_local/
│   │   ├── benchmark-results.csv
│   │   ├── system-info.json
│   │   └── charts/
│   └── 2024-01-16_vast_ai_rtx4090/
│       ├── benchmark-results.csv
│       ├── system-info.json
│       └── charts/
├── comparisons/
│   ├── mac_vs_vast_ai_comparison.png
│   └── hardware_performance_analysis.csv
└── archive/
    └── old_results/
```

### Phase 3: Cross-Platform Configuration
**Platform-Specific Optimization:**
```python
def get_platform_benchmark_config() -> Dict[str, Any]:
    """Platform-specific benchmark configuration"""
    import platform
    import torch

    if platform.system() == 'Darwin':  # Mac
        return {
            'concurrency_levels': [1, 2, 4],  # Conservative for Mac
            'requests_per_test': 100,  # Smaller for faster iteration
            'timeout': 30,
            'max_models': 2,  # Avoid overwhelming Mac
            'note': 'Mac local development testing'
        }
    elif torch.cuda.is_available():  # Vast.ai GPU VM
        return {
            'concurrency_levels': [1, 2, 4, 8, 16, 32],  # Full range
            'requests_per_test': 1000,  # Full benchmark
            'timeout': 120,
            'max_models': 5,  # Can handle more models
            'note': 'Vast.ai GPU VM production testing'
        }
    else:  # CPU fallback
        return {
            'concurrency_levels': [1, 2],  # Very conservative
            'requests_per_test': 50,
            'timeout': 60,
            'max_models': 1,
            'note': 'CPU fallback mode'
        }
```

### Phase 4: GPU Memory Monitoring
**Real-time VRAM Tracking:**
```python
def monitor_gpu_during_benchmark(stage: str) -> Dict[str, Any]:
    """Monitor GPU memory and utilization during benchmarks"""
    gpu_info = {'stage': stage, 'timestamp': time.time()}

    try:
        import torch
        if torch.cuda.is_available():
            gpu_info.update({
                'vram_allocated_mb': torch.cuda.memory_allocated() // (1024**2),
                'vram_reserved_mb': torch.cuda.memory_reserved() // (1024**2),
                'gpu_utilization': get_gpu_utilization(),  # Using nvidia-ml-py if available
            })
    except Exception as e:
        gpu_info['error'] = str(e)

    return gpu_info
```

## Specific Enhancement Areas Based on Your Requirements

### 1. Hardware Info in Chart Headers ✅
- **Enhancement**: Add system specs to all chart titles
- **Implementation**: Modify `_plot_multi()` and `_plot_single()` in `plot_results.py`
- **Example**: "Throughput vs Concurrency\nVast.ai RTX 4090 24GB | Ubuntu 22.04"

### 2. Better Result Organization ✅
- **Current Issue**: Files scattered in results/ directory
- **Solution**: Timestamped run directories with system metadata
- **Benefits**: Easy comparison between Mac and Vast.ai results

### 3. Chart Enhancement ✅
- **Professional Charts**: Already good, enhance with hardware context
- **Comparison Charts**: Mac vs Vast.ai performance comparisons
- **Time Series**: Track performance across different runs

### 4. Cross-Platform Testing Workflow ✅
- **Mac Phase**: Quick validation with smaller test parameters
- **Vast.ai Phase**: Full throughput testing with complete concurrency ranges
- **Comparison**: Automated comparison generation between platforms

## Implementation Roadmap

### File Modifications:
1. **`load-testing/openai_llm_benchmark.py`**:
   - Add hardware detection and platform-specific configuration
   - Include GPU memory monitoring hooks
   - Enhanced result metadata with system information

2. **`load-testing/results/plot_results.py`**:
   - Add hardware info to chart titles
   - Create organized output directories
   - Generate comparison charts between platforms

3. **New: `load-testing/system_monitor.py`**:
   - GPU memory monitoring utilities
   - Hardware information collection
   - Platform detection and configuration

## Success Criteria & Validation

### Quantitative Targets:
- **Chart Headers**: All charts include hardware specifications
- **Result Organization**: Timestamped directories with clear structure
- **GPU Monitoring**: VRAM usage tracked throughout benchmark runs
- **Cross-Platform**: Successful benchmarks on both Mac and Vast.ai

### Professional Presentation:
- **Thesis Quality**: Charts suitable for academic presentation
- **Hardware Context**: Clear indication of testing environment
- **Performance Comparison**: Easy comparison between platforms
- **Reproducibility**: Complete system information for result reproduction

This approach transforms your already sophisticated throughput testing into a professional, cross-platform benchmark suite suitable for thesis documentation and production deployment validation.
