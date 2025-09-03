# RAG Benchmarking Agent Instructions

## MANDATORY: Planning Approval Process
**BEFORE WRITING ANY CODE:**
1. Create detailed implementation plan using template in `.cursorrules`
2. Present plan to user for approval
3. Wait for explicit user confirmation before proceeding
4. Only execute code after receiving approval

## Role
You are a RAG evaluation specialist using RAGAS framework with expertise in cross-platform GPU memory management for Mac local testing and Vast.ai GPU VM deployment (12GB VRAM constraints).

## Current Implementation Analysis

**Existing Strengths in `src/benchmark.py`:**
- ✅ **Model Unloading Functions**: `stop_ollama_model()` and `stop_models_by_base_name()` already implemented
- ✅ **Memory Optimization**: Streaming testset loading, batch processing, chunked dataset creation
- ✅ **RAGAS Integration**: Complete 4-metric evaluation (faithfulness, answer_relevancy, context_precision, context_recall)
- ✅ **Parallel Evaluation**: ThreadPoolExecutor for efficient metric processing
- ✅ **Robust Retry Logic**: Exponential backoff with metric-specific configurations
- ✅ **Cloud Judge**: GPT-4o-mini via LiteLLM for reliable evaluation

**Critical GPU Memory Issues:**
- **Missing Systematic Cleanup**: Model unloading functions exist but aren't actively used between tests
- **Embedding Model Accumulation**: `keep_alive=0` set but models still accumulate in VRAM
- **Cross-Test Memory Leaks**: No cleanup between different model/embedding combinations
- **Evaluation Memory Pressure**: Parallel metrics + embedding models can exceed 12GB VRAM

## Enhanced GPU Memory Management Strategy

### Phase 1: Active Model Lifecycle Management
**Implement Strategic Model Unloading:**
```python
def ensure_clean_gpu_state(base_url: str, current_models: List[str]) -> None:
    """Aggressively clean GPU memory before each evaluation cycle"""
    # 1. Stop all loaded models
    loaded = get_ollama_loaded_models(base_url)
    for model in loaded:
        stop_ollama_model(base_url, model)

    # 2. Force garbage collection
    import gc; gc.collect()

    # 3. Add GPU memory monitoring
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        memory_info = torch.cuda.memory_summary()
        print(f"GPU Memory after cleanup: {memory_info}")
```

### Phase 2: Memory-Aware Evaluation Pipeline
**Strategic Evaluation Order:**
1. **Sequential Model Testing**: One model fully complete before next (vs parallel model testing)
2. **Embedding Model Cycling**: Clean unload between different embedding models
3. **Evaluation Batch Sizing**: Reduce batch sizes under memory pressure
4. **Memory Pressure Detection**: Monitor VRAM usage and adapt strategy

### Phase 3: Cross-Platform Monitoring & Recovery
**GPU Memory Monitoring Integration:**
```python
def monitor_gpu_memory(stage: str) -> Dict[str, Any]:
    """Monitor GPU memory at key benchmarking stages - works on Mac (CPU) and Vast.ai (GPU)"""
    memory_info = {'stage': stage, 'timestamp': datetime.now().isoformat()}

    # GPU monitoring for Vast.ai (NVIDIA)
    try:
        import torch
        if torch.cuda.is_available():
            memory_info.update({
                'platform': 'cuda',
                'allocated': torch.cuda.memory_allocated(),
                'reserved': torch.cuda.memory_reserved(),
                'max_allocated': torch.cuda.max_memory_allocated(),
            })
            print(f"GPU Memory [{stage}]: {memory_info['allocated']/1e9:.2f}GB allocated, {memory_info['reserved']/1e9:.2f}GB reserved")
        else:
            memory_info.update({'platform': 'cpu', 'note': 'GPU not available - likely Mac local testing'})
            print(f"Memory [{stage}]: Running on CPU (Mac local testing)")
    except ImportError:
        memory_info.update({'platform': 'cpu', 'note': 'PyTorch not available'})
        print(f"Memory [{stage}]: PyTorch not available - CPU mode")

    # Mac MPS detection (Apple Silicon)
    try:
        import torch
        if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            memory_info.update({'platform': 'mps', 'note': 'Apple Silicon MPS available'})
            print(f"Memory [{stage}]: Apple Silicon MPS detected")
    except:
        pass

    return memory_info
```

## Specific Implementation Enhancements

### Critical Integration Points in `benchmark.py`:

1. **Pre-Evaluation Cleanup** (Line ~331):
```python
# Before each model evaluation
print(f"\n--- Benchmarking Model: {model_name} with embedding {embedding_model} ---")

# ENHANCEMENT: Add aggressive memory cleanup
ensure_clean_gpu_state(OLLAMA_HOST_URL, [])
memory_pre = monitor_gpu_memory(f"pre_eval_{model_name}")
```

2. **Post-Evaluation Cleanup** (Line ~477):
```python
# After each model evaluation
print(f"Evaluation complete for {model_name}")
loaded = get_ollama_loaded_models(OLLAMA_HOST_URL)

# ENHANCEMENT: Force cleanup after each evaluation
stop_models_by_base_name(OLLAMA_HOST_URL, model_name.split('/')[-1])
memory_post = monitor_gpu_memory(f"post_eval_{model_name}")
```

3. **Embedding Model Transitions** (Line ~322):
```python
for embedding_model in EMBEDDING_MODELS:
    print(f"\n=== Retrieval Embedding: {embedding_model} ===")

    # ENHANCEMENT: Clean transition between embedding models
    ensure_clean_gpu_state(OLLAMA_HOST_URL, [])
    memory_embedding = monitor_gpu_memory(f"embedding_switch_{embedding_model}")
```

### Memory-Aware Configuration:
```python
# Enhanced configuration for 12GB VRAM
MEMORY_AWARE_CONFIG = {
    'max_parallel_metrics': 2,  # Reduce from 4 to prevent memory competition
    'batch_size_limit': 3,      # Smaller batches under memory pressure
    'evaluation_timeout': 900,  # Longer timeout for memory-constrained evaluation
    'memory_threshold_gb': 10,  # Trigger cleanup at 10GB usage
}
```

## Success Criteria & Validation

### Quantitative Targets:
- **Zero GPU OOM crashes** during multi-model evaluation
- **<10GB peak VRAM usage** across all evaluation stages
- **Successful completion** of all model/embedding combinations
- **Consistent memory baseline** (return to <2GB) between evaluations

### Monitoring & Reporting:
- **GPU Memory Tracking**: Log memory usage at all critical stages
- **Model Load/Unload Logs**: Verify proper lifecycle management
- **Evaluation Success Rate**: Track completion rates vs memory issues
- **Performance Impact**: Measure evaluation time vs memory safety trade-offs

### Test Validation Scenarios:
1. **Sequential Model Testing**: Test 3+ models sequentially without memory accumulation
2. **Multiple Embedding Models**: Switch between all-minilm, nomic-embed-text, bge-m3
3. **Extended Evaluation**: Run 100-question testset without memory crashes
4. **Recovery Testing**: Verify graceful recovery from memory pressure situations

## Enhanced File Structure:
- **Main Implementation**: `src/benchmark.py` with memory management enhancements
- **Memory Utils**: Add GPU monitoring utilities to benchmark module
- **Results Enhancement**: Include memory usage logs in result outputs
- **Config**: Add memory-aware configuration options

## Cross-Platform Deployment Strategy:

### Mac Local Testing (Development):
- **CPU/MPS Mode**: Graceful fallback when CUDA unavailable
- **Model Size Limits**: Test with smaller models for faster iteration
- **Memory Monitoring**: Track system RAM instead of VRAM
- **Validation**: Ensure pipeline works end-to-end before VM deployment

### Vast.ai GPU VM (Production):
- **CUDA Optimization**: Full GPU memory management and monitoring
- **12GB VRAM Constraints**: Aggressive model cleanup and memory-aware batching
- **Instance Monitoring**: Log GPU specifications for reproducibility
- **Network Resilience**: Handle network interruptions gracefully
- **Cost Optimization**: Minimize evaluation time while ensuring memory safety

### Platform Detection & Adaptation:
```python
def get_platform_config() -> Dict[str, Any]:
    """Auto-detect platform and return appropriate configuration"""
    import platform
    import torch

    config = {'os': platform.system()}

    if torch.cuda.is_available():
        config.update({
            'platform': 'vast_ai_gpu',
            'device': 'cuda',
            'memory_management': 'aggressive',
            'batch_size': 3,
            'parallel_metrics': 2
        })
    elif platform.system() == 'Darwin':  # Mac
        config.update({
            'platform': 'mac_local',
            'device': 'mps' if torch.backends.mps.is_available() else 'cpu',
            'memory_management': 'relaxed',
            'batch_size': 5,
            'parallel_metrics': 4
        })
    else:
        config.update({
            'platform': 'cpu_fallback',
            'device': 'cpu',
            'memory_management': 'minimal',
            'batch_size': 10,
            'parallel_metrics': 4
        })

    return config
```

This approach ensures your RAGAS infrastructure works seamlessly across Mac development environment and Vast.ai production deployment with appropriate optimizations for each platform.
