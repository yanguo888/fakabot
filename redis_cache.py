#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Redis缓存模块
提供商品信息、配置、用户会话等数据的缓存功能
"""

import redis
import json
import os
from typing import Any, Optional
from functools import wraps
import time

# Redis连接配置
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)

# 缓存过期时间配置（秒）
CACHE_TTL = {
    'product': 300,        # 商品信息：5分钟
    'config': 600,         # 配置信息：10分钟
    'user_session': 3600,  # 用户会话：1小时
    'rate_limit': 60,      # 频率限制：1分钟
    'stock': 30,           # 库存信息：30秒
}


class RedisCache:
    """Redis缓存管理类"""
    
    def __init__(self):
        self.enabled = False
        self.client = None
        self._connect()
    
    def _connect(self):
        """连接Redis"""
        try:
            self.client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                password=REDIS_PASSWORD,
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
                retry_on_timeout=True,
                health_check_interval=30
            )
            # 测试连接
            self.client.ping()
            self.enabled = True
            print(f"✅ Redis连接成功: {REDIS_HOST}:{REDIS_PORT}")
        except Exception as e:
            self.enabled = False
            print(f"⚠️ Redis连接失败，缓存功能已禁用: {e}")
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        if not self.enabled:
            return None
        
        try:
            value = self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            print(f"❌ Redis GET失败: {key}, {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """设置缓存"""
        if not self.enabled:
            return False
        
        try:
            json_value = json.dumps(value, ensure_ascii=False)
            if ttl:
                self.client.setex(key, ttl, json_value)
            else:
                self.client.set(key, json_value)
            return True
        except Exception as e:
            print(f"❌ Redis SET失败: {key}, {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        if not self.enabled:
            return False
        
        try:
            self.client.delete(key)
            return True
        except Exception as e:
            print(f"❌ Redis DELETE失败: {key}, {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """检查key是否存在"""
        if not self.enabled:
            return False
        
        try:
            return self.client.exists(key) > 0
        except Exception:
            return False
    
    def incr(self, key: str, amount: int = 1) -> Optional[int]:
        """递增计数器"""
        if not self.enabled:
            return None
        
        try:
            return self.client.incrby(key, amount)
        except Exception as e:
            print(f"❌ Redis INCR失败: {key}, {e}")
            return None
    
    def expire(self, key: str, ttl: int) -> bool:
        """设置过期时间"""
        if not self.enabled:
            return False
        
        try:
            return self.client.expire(key, ttl)
        except Exception:
            return False
    
    def ttl(self, key: str) -> int:
        """获取剩余过期时间"""
        if not self.enabled:
            return -1
        
        try:
            return self.client.ttl(key)
        except Exception:
            return -1


# 全局缓存实例
cache = RedisCache()


# 缓存装饰器
def cached(key_prefix: str, ttl: int = 300):
    """
    缓存装饰器
    
    使用示例:
    @cached('product', ttl=300)
    def get_product(pid):
        return db.query(...)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存key
            cache_key = f"{key_prefix}:{':'.join(map(str, args))}"
            
            # 尝试从缓存获取
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # 缓存未命中，执行函数
            result = func(*args, **kwargs)
            
            # 写入缓存
            if result is not None:
                cache.set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator


# 商品缓存
def get_product_cached(cur, pid: str):
    """获取商品信息（带缓存）"""
    cache_key = f"product:{pid}"
    
    # 尝试从缓存获取
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    # 缓存未命中，查询数据库
    try:
        row = cur.execute(
            "SELECT id, name, price, cover_url, full_description, status FROM products WHERE id=?",
            (pid,)
        ).fetchone()
        
        if row:
            product = {
                'id': row[0],
                'name': row[1],
                'price': row[2],
                'cover_url': row[3],
                'full_description': row[4],
                'status': row[5]
            }
            # 写入缓存
            cache.set(cache_key, product, CACHE_TTL['product'])
            return product
    except Exception as e:
        print(f"❌ 查询商品失败: {e}")
    
    return None


def invalidate_product_cache(pid: str):
    """清除商品缓存"""
    cache.delete(f"product:{pid}")


# 配置缓存
def get_setting_cached(cur, key: str, default: str = "") -> str:
    """获取配置（带缓存）"""
    cache_key = f"setting:{key}"
    
    # 尝试从缓存获取
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    
    # 缓存未命中，查询数据库
    try:
        row = cur.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        value = row[0] if row else default
        
        # 写入缓存
        cache.set(cache_key, value, CACHE_TTL['config'])
        return value
    except Exception:
        return default


def invalidate_setting_cache(key: str):
    """清除配置缓存"""
    cache.delete(f"setting:{key}")


# 用户会话缓存
def set_user_session(user_id: int, data: dict, ttl: int = None):
    """设置用户会话数据"""
    cache_key = f"session:{user_id}"
    cache.set(cache_key, data, ttl or CACHE_TTL['user_session'])


def get_user_session(user_id: int) -> Optional[dict]:
    """获取用户会话数据"""
    cache_key = f"session:{user_id}"
    return cache.get(cache_key)


def clear_user_session(user_id: int):
    """清除用户会话"""
    cache.delete(f"session:{user_id}")


if __name__ == "__main__":
    # 测试Redis连接
    print("测试Redis连接...")
    print(f"Redis状态: {'✅ 已启用' if cache.enabled else '❌ 已禁用'}")
    
    if cache.enabled:
        # 测试基本操作
        cache.set("test_key", {"hello": "world"}, 10)
        value = cache.get("test_key")
        print(f"测试读写: {value}")
        
        # 测试计数器
        count = cache.incr("test_counter")
        print(f"测试计数器: {count}")
        
        # 清理测试数据
        cache.delete("test_key")
        cache.delete("test_counter")
        print("✅ Redis测试通过")

