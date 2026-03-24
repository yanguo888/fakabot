#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""
柠檬支付官方标准对接模块
严格按照官方文档 https://api.lemzf.com/doc.html 实现
支持页面跳转支付和API接口支付
"""

import hashlib
import requests
import time
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlencode


class LemzfPayment:
    """柠檬支付官方标准对接类"""
    
    def __init__(self, merchant_id: str, key: str, gateway: str = None, api_gateway: str = None):
        """
        初始化柠檬支付
        
        Args:
            merchant_id: 商户ID
            key: 商户密钥
            gateway: 页面跳转网关 (submit.php)
            api_gateway: API接口网关 (mapi.php)
        """
        self.merchant_id = merchant_id
        self.key = key
        self.gateway = gateway or "https://a1004a.lempay.com/submit.php"
        self.api_gateway = api_gateway or "https://a1004a.lempay.com/mapi.php"
    
    def md5_sign(self, params: Dict[str, Any]) -> str:
        """
        MD5签名算法 - 严格按照官方文档实现
        
        1. 参数按ASCII码从小到大排序
        2. 排除sign、sign_type、值为空或0的参数
        3. 拼接为a=b&c=d格式
        4. 末尾拼接KEY，进行MD5加密，结果小写
        
        Args:
            params: 参数字典
            
        Returns:
            str: MD5签名
        """
        # 过滤参数：排除sign、sign_type、值为空或0的参数
        filtered_params = {}
        for k, v in params.items():
            if k in ('sign', 'sign_type'):
                continue
            if v is None or v == '' or v == 0 or str(v) == '0':
                continue
            filtered_params[k] = v
        
        # 按ASCII码排序
        sorted_params = sorted(filtered_params.items())
        
        # 拼接为URL键值对格式
        param_str = '&'.join([f"{k}={v}" for k, v in sorted_params])
        
        # 拼接商户密钥
        sign_str = param_str + self.key
        
        # MD5加密，结果小写
        return hashlib.md5(sign_str.encode('utf-8')).hexdigest().lower()
    
    def create_page_payment(self, order_id: str, amount: float, subject: str, 
                           notify_url: str, return_url: str = None, 
                           payment_type: str = None, device: str = "mobile") -> str:
        """
        创建页面跳转支付链接
        
        Args:
            order_id: 商户订单号
            amount: 支付金额
            subject: 订单标题
            notify_url: 异步通知地址
            return_url: 同步跳转地址
            payment_type: 支付方式 (alipay/wxpay/usdt等)
            device: 设备类型 (mobile/pc)
            
        Returns:
            str: 支付链接
        """
        params = {
            'pid': self.merchant_id,
            'type': payment_type,
            'out_trade_no': order_id,
            'notify_url': notify_url,
            'name': subject,
            'money': f"{amount:.2f}",
            'device': device
        }
        
        # 添加return_url（如果提供）
        if return_url:
            params['return_url'] = return_url
        
        # 生成签名
        params['sign'] = self.md5_sign(params)
        params['sign_type'] = 'MD5'
        
        # 构建支付链接
        query_string = urlencode(params)
        return f"{self.gateway}?{query_string}"
    
    def create_api_payment(self, order_id: str, amount: float, subject: str,
                          notify_url: str, payment_type: str, device: str = "mobile", 
                          client_ip: str = "127.0.0.1") -> Dict[str, Any]:
        """
        创建API接口支付
        
        Args:
            order_id: 商户订单号
            amount: 支付金额
            subject: 订单标题
            notify_url: 异步通知地址
            payment_type: 支付方式
            device: 设备类型
            
        Returns:
            Dict: API响应结果
        """
        params = {
            'pid': self.merchant_id,
            'type': payment_type,
            'out_trade_no': order_id,
            'notify_url': notify_url,
            'name': subject,
            'money': f"{amount:.2f}",
            'device': device,
            'clientip': client_ip
        }
        
        # 生成签名
        params['sign'] = self.md5_sign(params)
        params['sign_type'] = 'MD5'
        
        try:
            # 发送POST请求
            response = requests.post(self.api_gateway, data=params, timeout=30)
            response.raise_for_status()
            
            # 解析JSON响应
            result = response.json()
            return result
            
        except requests.RequestException as e:
            return {
                'code': -1,
                'msg': f'网络请求失败: {str(e)}',
                'data': None
            }
        except ValueError as e:
            return {
                'code': -1,
                'msg': f'响应解析失败: {str(e)}',
                'data': None
            }
    
    def verify_callback(self, params: Dict[str, Any]) -> bool:
        """
        验证回调签名
        
        Args:
            params: 回调参数
            
        Returns:
            bool: 签名是否有效
        """
        if 'sign' not in params:
            return False
        
        received_sign = params['sign']
        calculated_sign = self.md5_sign(params)
        
        return received_sign.lower() == calculated_sign.lower()
    
    def query_order(self, out_trade_no: str) -> Dict[str, Any]:
        """
        查询单个订单
        
        Args:
            out_trade_no: 商户订单号
            
        Returns:
            Dict: 查询结果
        """
        params = {
            'pid': self.merchant_id,
            'out_trade_no': out_trade_no
        }
        
        sign = self.md5_sign(params)
        query_url = f"https://a1004a.lempay.com/api.php?act=order&pid={self.merchant_id}&out_trade_no={out_trade_no}&sign={sign}"
        
        try:
            response = requests.get(query_url, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {
                'code': -1,
                'msg': f'查询失败: {str(e)}'
            }


def create_lemzf_payment(config: Dict[str, Any]) -> LemzfPayment:
    """
    创建柠檬支付实例的工厂函数
    
    Args:
        config: 支付配置
        
    Returns:
        LemzfPayment: 柠檬支付实例
    """
    return LemzfPayment(
        merchant_id=config['merchant_id'],
        key=config['key'],
        gateway=config.get('gateway'),
        api_gateway=config.get('api_gateway')
    )


def create_payment(config: Dict[str, Any], order_id: str, amount: float, 
                  subject: str, notify_url: str, return_url: str = None, 
                  client_ip: str = "127.0.0.1") -> Tuple[bool, str]:
    """
    创建柠檬支付订单 - 兼容原有接口
    
    Args:
        config: 支付配置
        order_id: 订单号
        amount: 金额
        subject: 标题
        notify_url: 通知地址
        return_url: 返回地址
        
    Returns:
        Tuple[bool, str]: (是否成功, 支付链接或错误信息)
    """
    try:
        lemzf = create_lemzf_payment(config)
        
        # 获取支付方式
        payment_type = config.get('type', 'alipay')
        device = config.get('device', 'mobile')
        
        # 优先使用API接口支付
        if config.get('api_gateway'):
            result = lemzf.create_api_payment(
                order_id=order_id,
                amount=amount,
                subject=subject,
                notify_url=notify_url,
                payment_type=payment_type,
                device=device,
                client_ip=client_ip
            )
            
            if result.get('code') == 1:
                data = result.get('data', result)
                # 优先使用官方短链接 (cashier.php)
                payurl = data.get('payurl', '')
                qrcode = data.get('qrcode', '')
                urlscheme = data.get('urlscheme', '')
                
                # 优先级：cashier.php短链接 > 其他payurl > qrcode > urlscheme
                if payurl and 'cashier.php' in payurl:
                    print(f"✅ 使用官方短链接: {len(payurl)} 字符")
                    return True, payurl
                elif payurl:
                    print(f"✅ 使用官方支付链接: {len(payurl)} 字符")
                    return True, payurl
                elif qrcode:
                    print(f"✅ 使用官方二维码链接: {len(qrcode)} 字符")
                    return True, qrcode
                elif urlscheme:
                    print(f"✅ 使用原生协议链接: {len(urlscheme)} 字符")
                    return True, urlscheme
            
            # API失败时记录错误但继续尝试页面跳转
            print(f"⚠️ API支付失败: {result.get('msg', '未知错误')}")
        
        # 使用页面跳转支付作为备用方案
        payment_url = lemzf.create_page_payment(
            order_id=order_id,
            amount=amount,
            subject=subject,
            notify_url=notify_url,
            return_url=return_url,
            payment_type=payment_type,
            device=device
        )
        
        return True, payment_url
        
    except Exception as e:
        error_msg = f"柠檬支付创建失败: {str(e)}"
        print(f"❌ {error_msg}")
        return False, error_msg


def verify_lemzf_callback(config: Dict[str, Any], params: Dict[str, Any]) -> bool:
    """
    验证柠檬支付回调 - 兼容原有接口
    
    Args:
        config: 支付配置
        params: 回调参数
        
    Returns:
        bool: 验证是否通过
    """
    try:
        lemzf = create_lemzf_payment(config)
        return lemzf.verify_callback(params)
    except Exception as e:
        print(f"❌ 柠檬支付回调验证失败: {str(e)}")
        return False


# 支付方式映射
LEMZF_PAYMENT_TYPES = {
    'alipay': 'alipay',      # 支付宝
    'wxpay': 'wxpay',        # 微信支付
    'usdt': 'usdt',          # USDT
    'qqpay': 'qqpay',        # QQ钱包
    'bank': 'bank',          # 网银支付
}

# 设备类型映射
LEMZF_DEVICE_TYPES = {
    'mobile': 'mobile',      # 手机
    'pc': 'pc',             # 电脑
}

if __name__ == "__main__":
    # 测试代码
    config = {
        'merchant_id': '1506',
        'key': 'test_key',
        'gateway': 'https://66101506.lemzf.com/submit.php',
        'api_gateway': 'https://66101506.lemzf.com/mapi.php',
        'type': 'alipay',
        'device': 'mobile'
    }
    
    # 测试创建支付
    success, result = create_payment(
        config=config,
        order_id='TEST001',
        amount=99.99,
        subject='测试订单',
        notify_url='https://example.com/notify'
    )
    
    print(f"创建支付: {'成功' if success else '失败'}")
    print(f"结果: {result}")
    
    # 测试签名验证
    test_params = {
        'pid': '1506',
        'trade_no': '2024100400001',
        'out_trade_no': 'TEST001',
        'type': 'alipay',
        'name': '测试订单',
        'money': '99.99',
        'trade_status': 'TRADE_SUCCESS',
        'sign': 'test_sign'
    }
    
    lemzf = create_lemzf_payment(config)
    calculated_sign = lemzf.md5_sign(test_params)
    print(f"计算签名: {calculated_sign}")

