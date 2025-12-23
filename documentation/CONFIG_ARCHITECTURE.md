# Configuration Architecture Improvement

## Overview

The configuration system has been refactored from module-level globals to a class-based approach using `ConfigManager`. This addresses the "Global State Management" design concern.

## Before (Problematic)

```python
# core/config.py
_global_config = None
_config_home = None

def load_global_config():
    global _global_config
    if _global_config is None:
        # Load config...
    return _global_config
```

### Problems with Global State

1. **Testing Issues**
   - Cannot easily test with different configurations
   - Tests can interfere with each other
   - No way to reset state between tests

2. **Thread Safety**
   - Multiple threads share the same globals
   - Can cause race conditions in parallel execution

3. **Hidden Dependencies**
   - Functions depend on global state that isn't visible in signatures
   - Hard to understand data flow

4. **No Encapsulation**
   - State is scattered across module
   - No clear ownership of configuration data

## After (Improved)

```python
# core/config.py
class ConfigManager:
    """Configuration manager for signalbox."""
    
    def __init__(self, config_home=None):
        self._config_home = config_home
        self._global_config = None
    
    def load_global_config(self):
        if self._global_config is None:
            # Load config...
        return self._global_config
    
    def reset(self):
        """Reset cached configuration."""
        self._global_config = None
        self._config_home = None

# Default instance for backward compatibility
_default_config_manager = ConfigManager()

# Convenience functions
def load_global_config():
    return _default_config_manager.load_global_config()
```

### Benefits of Class-Based Approach

1. **Better Testability**
   ```python
   def test_custom_config():
       # Create isolated instance for testing
       config = ConfigManager(config_home='/tmp/test')
       assert config.find_config_home() == '/tmp/test'
       config.reset()  # Clean up after test
   ```

2. **Thread Safety**
   ```python
   def worker_thread():
       # Each thread can have its own config instance
       local_config = ConfigManager()
       config = local_config.load_config()
   ```

3. **Explicit Dependencies**
   ```python
   def process_scripts(config_manager):
       # Dependency is explicit in function signature
       scripts = config_manager.load_config()['scripts']
   ```

4. **Encapsulation**
   ```python
   class ConfigManager:
       # All state is contained within the class
       def __init__(self):
           self._config_home = None      # Private
           self._global_config = None    # Private
   ```

## Backward Compatibility

The module-level functions are maintained for backward compatibility:

```python
# Old code still works
from core.config import load_config, get_config_value

config = load_config()
timeout = get_config_value('execution.default_timeout')
```

## Advanced Usage

### Custom Configuration Location

```python
# Create config manager with custom location
config = ConfigManager(config_home='/etc/signalbox')
scripts = config.load_config()
```

### Multiple Configurations

```python
# Manage multiple configurations simultaneously
prod_config = ConfigManager(config_home='/etc/signalbox/prod')
dev_config = ConfigManager(config_home='/etc/signalbox/dev')

prod_scripts = prod_config.load_config()
dev_scripts = dev_config.load_config()
```

### Testing with Isolation

```python
def test_with_temp_config(tmpdir):
    # Create isolated configuration for test
    config = ConfigManager(config_home=str(tmpdir))
    
    # Test operations
    result = config.load_global_config()
    assert result == {}
    
    # Clean up
    config.reset()
```

## Implementation Details

### State Management

```python
class ConfigManager:
    def __init__(self, config_home=None):
        # Instance variables (not globals)
        self._config_home = config_home
        self._global_config = None
    
    def find_config_home(self):
        # Caching still works, but per-instance
        if self._config_home is not None:
            return self._config_home
        # ... find logic
        return self._config_home
```

### Lazy Loading

Configuration is still loaded lazily (only when needed):

```python
def load_global_config(self):
    if self._global_config is None:  # Check instance variable
        # Load configuration
        self._global_config = yaml.safe_load(f)
    return self._global_config
```

### Reset Capability

```python
def reset(self):
    """Reset cached configuration (useful for testing or reload)."""
    self._global_config = None
    self._config_home = None
```

## Migration Guide

### For New Code

Use `ConfigManager` directly:

```python
from core.config import ConfigManager

def my_function():
    config_mgr = ConfigManager()
    config = config_mgr.load_config()
```

### For Existing Code

No changes needed - module functions still work:

```python
from core.config import load_config, get_config_value

def existing_function():
    config = load_config()  # Still works!
```

### For Tests

Create isolated instances:

```python
def test_configuration():
    # Create test-specific instance
    config = ConfigManager(config_home='/tmp/test_config')
    
    # Run tests
    result = config.load_global_config()
    
    # Clean up
    config.reset()
```

## Comparison with Other Patterns

### Singleton Pattern

❌ **Not Used**: Singletons have similar issues to globals (hard to test, hidden state)

✅ **Our Approach**: Default instance for convenience, but users can create new instances

### Dependency Injection

✅ **Supported**: Can pass `ConfigManager` instances to functions

```python
def process_scripts(config_manager: ConfigManager):
    scripts = config_manager.load_config()['scripts']
    # ... process scripts
```

### Context Managers

🔄 **Future Enhancement**: Could add context manager support

```python
with ConfigManager(config_home='/tmp/test') as config:
    scripts = config.load_config()
    # Automatically resets on exit
```

## Performance Impact

- **Negligible**: Class instance creation is extremely fast
- **Caching Preserved**: Lazy loading and caching still work per-instance
- **Memory**: Minimal increase (one object vs. module-level variables)

## Testing Improvements

### Before

```python
def test_config():
    # Globals affect all tests
    config = load_config()
    # No way to reset between tests
```

### After

```python
def test_config():
    config_mgr = ConfigManager(config_home='/tmp/test')
    config = config_mgr.load_config()
    config_mgr.reset()  # Clean slate for next test
```

## Related Improvements

This change enables:

1. **Better Error Handling**: Can pass config manager to exception handlers
2. **Logging Integration**: Each config manager can have its own logger
3. **Plugin System**: Plugins can have independent configurations
4. **Multi-tenancy**: Support multiple independent configurations

## Summary

| Aspect | Before (Globals) | After (Class) |
|--------|-----------------|---------------|
| Testability | ❌ Difficult | ✅ Easy |
| Thread Safety | ⚠️ Risky | ✅ Safe |
| Encapsulation | ❌ Poor | ✅ Good |
| Flexibility | ❌ Limited | ✅ High |
| Backward Compat | ✅ N/A | ✅ Maintained |
| Performance | ✅ Fast | ✅ Fast |

The new `ConfigManager` class provides a solid foundation for future enhancements while maintaining complete backward compatibility with existing code.
