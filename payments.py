#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""
支付系统核心模块 - 重构版
- 柠檬支付：使用官方标准对接
- TOKEN188 USDT：保持原有逻辑不变
"""

import time
import hashlib
import requests
from typing import Tuple, Optional
from urllib.parse import urlencode
from payments_lemzf_official import create_payment as lemzf_create_payment, verify_lemzf_callback


def md5_sign_token188(params: dict, key: str) -> str:
    """TOKEN188 USDT MD5 签名算法"""
    # 排除sign字段，按key排序
    filtered_params = {k: v for k, v in params.items() if k != 'sign'}
    sorted_params = sorted(filtered_params.items())
    
    # 拼接字符串
    param_str = '&'.join([f"{k}={v}" for k, v in sorted_params])
    sign_str = param_str + key
    
    # MD5加密
    return hashlib.md5(sign_str.encode('utf-8')).hexdigest().upper()


def create_token188_payment(config: dict, order_id: str, amount: float, 
                           subject: str, notify_url: str) -> Tuple[bool, str]:
    """
    创建TOKEN188 USDT支付订单
    
    Args:
        config: TOKEN188配置
        order_id: 订单号
        amount: 金额
        subject: 订单标题
        notify_url: 回调地址
        
    Returns:
        Tuple[bool, str]: (是否成功, 支付链接或错误信息)
    """
    try:
        # TOKEN188支付参数
        params = {
            'merchantId': config['merchant_id'],
            'amount': f"{amount:.2f}",
            'chainType': config.get('chain_type', 'TRX'),
            'to': config['monitor_address'],
            'orderNo': order_id,
            'notifyUrl': notify_url,
            'returnUrl': notify_url.replace('/callback/token188', ''),
            'remark': subject
        }
        
        # 生成签名
        params['sign'] = md5_sign_token188(params, config['key'])
        
        # 构建支付链接
        gateway = "https://payweb.188pay.net/"
        payment_url = gateway + "?" + urlencode(params)
        
        return True, payment_url
        
    except Exception as e:
        error_msg = f"TOKEN188支付创建失败: {str(e)}"
        print(f"❌ {error_msg}")
        return False, error_msg


def create_payment(
    ch: dict,
    subject: str,
    amount: float,
    out_trade_no: str,
    domain: str,
    client_ip: str,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    统一支付创建接口
    
    Args:
        ch: 支付通道配置
        subject: 订单标题
        amount: 支付金额
        out_trade_no: 商户订单号
        domain: 域名
        client_ip: 客户端IP
        
    Returns:
        Tuple[bool, Optional[str], Optional[str]]: (是否成功, 支付链接, 错误信息)
    """
    try:
        # 构建回调地址
        if ch.get('route') == '/pay/token188':
            # TOKEN188 USDT支付
            notify_url = f"{domain}/callback/token188"
            success, result = create_token188_payment(
                config=ch,
                order_id=out_trade_no,
                amount=amount,
                subject=subject,
                notify_url=notify_url
            )
            return success, result if success else None, None if success else result
        else:
            # 柠檬支付 (支付宝、微信、USDT柠檬)
            notify_url = f"{domain}/callback"
            return_url = domain
            
            success, result = lemzf_create_payment(
                config=ch,
                order_id=out_trade_no,
                amount=amount,
                subject=subject,
                notify_url=notify_url,
                return_url=return_url,
                client_ip=client_ip
            )
            
            # 如果成功且配置了短链接，检查是否需要进一步优化
            if success and result and ch.get('use_short_url', False):
                try:
                    # 如果已经是官方短链接，就不需要再生成自建短链接
                    # 柠檬支付官方短链接格式：cashier.php, u.lemzf.com/checkout/, 等
                    is_official_short = (
                        'cashier.php' in result or 
                        'u.lemzf.com/checkout/' in result or
                        ('lemzf.com' in result and len(result) < 100)
                    )
                    
                    if is_official_short:
                        print(f"✅ 已使用柠檬支付官方短链接: {len(result)} 字符")
                        return True, result, None
                    
                    # 如果是长链接，则生成自建短链接
                    from user_flow import create_short_url
                    print(f"柠檬支付原链接长度: {len(result)} 字符")
                    short_url = create_short_url(result, out_trade_no)
                    if short_url and short_url != result:
                        print(f"柠檬支付自建短链接生成成功: {len(short_url)} 字符")
                        return True, short_url, None
                    else:
                        print("柠檬支付短链接生成失败，使用原链接")
                except Exception as e:
                    print(f"柠檬支付短链接处理异常: {e}")
            
            return success, result if success else None, None if success else result
            
    except Exception as e:
        error_msg = f"支付创建失败: {str(e)}"
        print(f"❌ {error_msg}")
        return False, None, error_msg


def verify_callback_signature(ch: dict, params: dict) -> bool:
    """
    验证支付回调签名
    
    Args:
        ch: 支付通道配置
        params: 回调参数
        
    Returns:
        bool: 签名验证结果
    """
    try:
        if ch.get('route') == '/pay/token188':
            # TOKEN188 USDT签名验证
            if 'sign' not in params:
                return False
            
            received_sign = params['sign']
            calculated_sign = md5_sign_token188(params, ch['key'])
            
            return received_sign.upper() == calculated_sign.upper()
        else:
            # 柠檬支付签名验证
            return verify_lemzf_callback(ch, params)
            
    except Exception as e:
        print(f"❌ 签名验证失败: {str(e)}")
        return False


# 向后兼容的函数别名
def md5_sign(params: dict, key: str) -> str:
    """向后兼容的MD5签名函数 - 使用柠檬支付标准算法"""
    from payments_lemzf_official import LemzfPayment
    
    # 创建临时实例进行签名计算
    temp_lemzf = LemzfPayment("", key)
    return temp_lemzf.md5_sign(params)


if __name__ == "__main__":
    # 测试代码
    print("支付系统模块加载成功")
    print("- 柠檬支付：支付宝、微信、USDT柠檬")
    print("- TOKEN188：USDT(TRC20)")

