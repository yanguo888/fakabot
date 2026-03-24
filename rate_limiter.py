#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
频率限制模块
防止恶意刷单、暴力攻击等
"""

import time
from typing import Optional, Tuple
from redis_cache import cache


class RateLimiter:
    """频率限制器"""
    
    # 限制规则配置
    RULES = {
        # 用户操作限制
        'user_command': {'limit': 20, 'window': 60, 'desc': '命令操作'},
        'user_payment': {'limit': 5, 'window': 300, 'desc': '创建订单'},
        'user_query': {'limit': 10, 'window': 60, 'desc': '查询订单'},
        
        # IP限制
        'ip_callback': {'limit': 100, 'window': 60, 'desc': '支付回调'},
        'ip_request': {'limit': 200, 'window': 60, 'desc': 'HTTP请求'},
        
        # 全局限制
        'global_order': {'limit': 1000, 'window': 60, 'desc': '全局订单创建'},
    }
    
    def __init__(self):
        self.enabled = cache.enabled
    
    def check_rate_limit(self, key: str, rule_name: str) -> Tuple[bool, Optional[str]]:
        """
        检查频率限制
        
        Args:
            key: 限制对象标识（如user_id, ip等）
            rule_name: 规则名称
        
        Returns:
            (是否允许, 错误消息)
        """
        if not self.enabled:
            return True, None
        
        rule = self.RULES.get(rule_name)
        if not rule:
            return True, None
        
        cache_key = f"rate_limit:{rule_name}:{key}"
        
        try:
            # 获取当前计数
            current = cache.get(cache_key)
            
            if current is None:
                # 首次访问，初始化计数器
                cache.set(cache_key, {'count': 1, 'start_time': int(time.time())}, rule['window'])
                return True, None
            
            # 检查时间窗口
            elapsed = int(time.time()) - current['start_time']
            
            if elapsed > rule['window']:
                # 时间窗口已过，重置计数器
                cache.set(cache_key, {'count': 1, 'start_time': int(time.time())}, rule['window'])
                return True, None
            
            # 在时间窗口内，检查计数
            if current['count'] >= rule['limit']:
                # 超过限制
                remaining = rule['window'] - elapsed
                error_msg = f"⚠️ {rule['desc']}过于频繁，请 {remaining} 秒后再试"
                return False, error_msg
            
            # 未超过限制，增加计数
            current['count'] += 1
            cache.set(cache_key, current, rule['window'])
            return True, None
            
        except Exception as e:
            print(f"❌ 频率限制检查失败: {e}")
            # 出错时放行，避免影响正常业务
            return True, None
    
    def get_remaining_quota(self, key: str, rule_name: str) -> dict:
        """
        获取剩余配额
        
        Returns:
            {'used': 已使用次数, 'limit': 限制次数, 'remaining': 剩余次数, 'reset_in': 重置时间(秒)}
        """
        if not self.enabled:
            return {'used': 0, 'limit': 999, 'remaining': 999, 'reset_in': 0}
        
        rule = self.RULES.get(rule_name)
        if not rule:
            return {'used': 0, 'limit': 999, 'remaining': 999, 'reset_in': 0}
        
        cache_key = f"rate_limit:{rule_name}:{key}"
        
        try:
            current = cache.get(cache_key)
            
            if current is None:
                return {
                    'used': 0,
                    'limit': rule['limit'],
                    'remaining': rule['limit'],
                    'reset_in': 0
                }
            
            elapsed = int(time.time()) - current['start_time']
            reset_in = max(0, rule['window'] - elapsed)
            
            return {
                'used': current['count'],
                'limit': rule['limit'],
                'remaining': max(0, rule['limit'] - current['count']),
                'reset_in': reset_in
            }
        except Exception:
            return {'used': 0, 'limit': 999, 'remaining': 999, 'reset_in': 0}
    
    def reset_limit(self, key: str, rule_name: str):
        """重置限制（管理员功能）"""
        cache_key = f"rate_limit:{rule_name}:{key}"
        cache.delete(cache_key)


# 全局限制器实例
rate_limiter = RateLimiter()


# 装饰器：用户命令限制
def rate_limit_user_command(func):
    """用户命令频率限制装饰器"""
    async def wrapper(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        
        allowed, error_msg = rate_limiter.check_rate_limit(str(user_id), 'user_command')
        
        if not allowed:
            try:
                await update.message.reply_text(error_msg)
            except Exception:
                pass
            return
        
        return await func(update, context, *args, **kwargs)
    
    return wrapper


# 装饰器：用户支付限制
def rate_limit_user_payment(func):
    """用户支付频率限制装饰器"""
    async def wrapper(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        
        allowed, error_msg = rate_limiter.check_rate_limit(str(user_id), 'user_payment')
        
        if not allowed:
            try:
                await update.callback_query.answer(error_msg, show_alert=True)
            except Exception:
                pass
            return
        
        return await func(update, context, *args, **kwargs)
    
    return wrapper


# IP限制检查
def check_ip_rate_limit(ip: str, rule_name: str = 'ip_request') -> Tuple[bool, Optional[str]]:
    """检查IP频率限制"""
    return rate_limiter.check_rate_limit(ip, rule_name)


if __name__ == "__main__":
    # 测试频率限制
    print("测试频率限制...")
    
    # 测试用户命令限制
    for i in range(25):
        allowed, msg = rate_limiter.check_rate_limit("test_user_123", "user_command")
        print(f"第{i+1}次请求: {'✅ 允许' if allowed else f'❌ 拒绝 - {msg}'}")
        
        if not allowed:
            # 查看剩余配额
            quota = rate_limiter.get_remaining_quota("test_user_123", "user_command")
            print(f"配额信息: {quota}")
            break
    
    print("\n✅ 频率限制测试完成")

