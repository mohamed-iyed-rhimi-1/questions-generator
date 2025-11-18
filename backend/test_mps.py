#!/usr/bin/env python3
"""
Quick test script to verify MPS (Apple Silicon GPU) support.
Run this before starting the application to ensure GPU acceleration works.
"""

import torch
import sys


def test_mps():
    print("=" * 60)
    print("Apple Silicon MPS GPU Test")
    print("=" * 60)
    
    # Check PyTorch version
    print(f"\n✓ PyTorch version: {torch.__version__}")
    
    # Check MPS availability
    mps_available = torch.backends.mps.is_available()
    mps_built = torch.backends.mps.is_built()
    
    print(f"✓ MPS built into PyTorch: {mps_built}")
    print(f"✓ MPS available on system: {mps_available}")
    
    if not mps_built:
        print("\n❌ ERROR: PyTorch was not built with MPS support")
        print("   Solution: Reinstall PyTorch with MPS support:")
        print("   pip install --upgrade torch torchvision torchaudio")
        return False
    
    if not mps_available:
        print("\n❌ ERROR: MPS not available on this system")
        print("   Requirements:")
        print("   - macOS 12.3 or later")
        print("   - Apple Silicon (M1/M2/M3) Mac")
        return False
    
    # Test MPS operations
    print("\n" + "=" * 60)
    print("Testing MPS Operations")
    print("=" * 60)
    
    try:
        # Create tensor on MPS
        print("\n1. Creating tensor on MPS device...")
        x = torch.ones(5, 5, device="mps")
        print(f"   ✓ Tensor created: shape={x.shape}, device={x.device}")
        
        # Perform computation
        print("\n2. Testing matrix multiplication...")
        y = torch.randn(5, 5, device="mps")
        z = torch.matmul(x, y)
        print(f"   ✓ Computation successful: result shape={z.shape}")
        
        # Test memory allocation
        print("\n3. Testing memory allocation...")
        large_tensor = torch.randn(1000, 1000, device="mps")
        print(f"   ✓ Large tensor allocated: {large_tensor.numel():,} elements")
        
        # Clean up
        del x, y, z, large_tensor
        torch.mps.empty_cache()
        print("   ✓ Memory cleaned up")
        
        print("\n" + "=" * 60)
        print("✅ SUCCESS: MPS GPU acceleration is working!")
        print("=" * 60)
        print("\nYour application will use Apple Silicon GPU for:")
        print("  • Whisper transcription (3-5x faster)")
        print("  • Sentence embeddings (2-3x faster)")
        print("\nYou can now start the application.")
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: MPS test failed: {e}")
        print("\nTroubleshooting:")
        print("  1. Update macOS to 12.3 or later")
        print("  2. Reinstall PyTorch: pip install --upgrade torch")
        print("  3. Restart your terminal/IDE")
        return False


def test_whisper_compatibility():
    """Test if Whisper can use MPS."""
    print("\n" + "=" * 60)
    print("Testing Whisper Compatibility")
    print("=" * 60)
    
    try:
        import whisper
        print(f"\n✓ Whisper installed: version {whisper.__version__}")
        
        # Try loading a small model on MPS
        print("\nLoading tiny Whisper model on MPS...")
        model = whisper.load_model("tiny", device="mps")
        print("✓ Whisper model loaded successfully on MPS!")
        
        # Clean up
        del model
        torch.mps.empty_cache()
        
        return True
        
    except ImportError:
        print("\n⚠ Whisper not installed yet")
        print("  Will be installed with: pip install -r requirements.txt")
        return True
    except Exception as e:
        print(f"\n⚠ Whisper MPS test failed: {e}")
        print("  This might be okay - will fallback to CPU if needed")
        return True


def test_sentence_transformers():
    """Test if sentence-transformers can use MPS."""
    print("\n" + "=" * 60)
    print("Testing Sentence Transformers Compatibility")
    print("=" * 60)
    
    try:
        from sentence_transformers import SentenceTransformer
        print("\n✓ Sentence Transformers installed")
        
        # Try loading model on MPS
        print("\nLoading embedding model on MPS...")
        model = SentenceTransformer('all-MiniLM-L6-v2', device='mps')
        print("✓ Embedding model loaded successfully on MPS!")
        
        # Test encoding
        print("\nTesting encoding...")
        embedding = model.encode("Test sentence", convert_to_numpy=True)
        print(f"✓ Encoding successful: embedding shape={embedding.shape}")
        
        # Clean up
        del model
        torch.mps.empty_cache()
        
        return True
        
    except ImportError:
        print("\n⚠ Sentence Transformers not installed yet")
        print("  Will be installed with: pip install -r requirements.txt")
        return True
    except Exception as e:
        print(f"\n⚠ Sentence Transformers MPS test failed: {e}")
        print("  This might be okay - will fallback to CPU if needed")
        return True


if __name__ == "__main__":
    print("\n")
    
    # Run basic MPS test
    mps_ok = test_mps()
    
    if not mps_ok:
        print("\n❌ Basic MPS test failed. Fix the issues above before continuing.")
        sys.exit(1)
    
    # Run optional compatibility tests
    test_whisper_compatibility()
    test_sentence_transformers()
    
    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Start the application: docker-compose up -d")
    print("  2. Check logs: docker-compose logs backend | grep MPS")
    print("  3. You should see 'Apple Silicon GPU (MPS) detected'")
    print("\n")
