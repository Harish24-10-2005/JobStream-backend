"""Verification test for DI Container and Event Bus."""
import asyncio
from src.core.container import Container, container, inject
from src.core.event_bus import EventBus, event_bus, Event

async def test():
    # === DI Container Tests ===
    c = Container()
    
    # Test singleton
    c.register_singleton("counter", lambda: {"count": 0})
    obj1 = c.resolve("counter")
    obj1["count"] += 1
    obj2 = c.resolve("counter")
    assert obj1 is obj2, "Singletons must return same instance"
    assert obj2["count"] == 1
    print("[PASS] DI: Singleton returns same instance")
    
    # Test factory
    c.register_factory("new_list", lambda: [])
    list1 = c.resolve("new_list")
    list2 = c.resolve("new_list")
    assert list1 is not list2, "Factories must return new instances"
    print("[PASS] DI: Factory returns new instances")
    
    # Test override
    c.override("counter", {"count": 999})
    assert c.resolve("counter")["count"] == 999
    c.clear_overrides()
    assert c.resolve("counter")["count"] == 1
    print("[PASS] DI: Test overrides work")
    
    # Test inject bridge
    resolver = inject("counter")
    # inject returns a callable
    assert callable(resolver)
    print("[PASS] DI: FastAPI inject bridge works")
    
    # Test health check
    health = c.health_check()
    assert health["counter"] == "initialized"
    print("[PASS] DI: Health check reports status")

    # === Event Bus Tests ===
    bus = EventBus()
    received = []
    
    @bus.on("test:event")
    async def handler(event: Event):
        received.append(event.data)
    
    await bus.emit("test:event", {"value": 42})
    assert len(received) == 1
    assert received[0]["value"] == 42
    print("[PASS] EventBus: Basic pub/sub works")
    
    # Wildcard
    wildcard_received = []
    @bus.on("test:*")
    async def wildcard_handler(event: Event):
        wildcard_received.append(event.topic)
    
    await bus.emit("test:wildcard_event", {"x": 1})
    assert "test:wildcard_event" in wildcard_received
    print("[PASS] EventBus: Wildcard matching works")
    
    # Stats
    assert bus.stats.get("test:event", 0) >= 1
    print("[PASS] EventBus: Stats tracking works")
    
    # History
    history = bus.history(limit=5)
    assert len(history) > 0
    print("[PASS] EventBus: Event history works")
    
    # Error isolation
    @bus.on("error:test")
    async def bad_handler(event: Event):
        raise ValueError("intentional error")
    
    @bus.on("error:test")
    async def good_handler(event: Event):
        received.append("good")
    
    await bus.emit("error:test", {})
    assert "good" in received, "Good handler should still run despite bad handler"
    print("[PASS] EventBus: Error isolation works")
    
    print("\n=== ALL DI + EVENT BUS TESTS PASSED ===")

asyncio.run(test())
