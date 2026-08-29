"""RoboParts SDK 异常定义。

所有 SDK 抛出的异常都继承自 :class:`RoboPartsError`，便于调用方使用
``except RoboPartsError`` 统一捕获。服务端返回的不同 HTTP 状态码会映射到
对应的子类异常：

    401 -> AuthenticationError      API Key 无效或缺失
    402 -> InsufficientCreditsError 积分不足
    404 -> NotFoundError            请求的资源不存在
    429 -> RateLimitError           请求频率超过限制
"""


class RoboPartsError(Exception):
    """基础异常，所有 RoboParts SDK 异常的父类。

    Attributes:
        message: 错误描述信息。
        status_code: 服务端返回的 HTTP 状态码（如果是 HTTP 错误）。
        response: 原始响应字典（如果可用），用于调试。
    """

    def __init__(self, message="", status_code=None, response=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response = response

    def __str__(self):
        if self.status_code is not None:
            return f"[{self.status_code}] {self.message}"
        return self.message


class AuthenticationError(RoboPartsError):
    """API Key 无效、缺失或未注册（HTTP 401 / 403）。"""


class InsufficientCreditsError(RoboPartsError):
    """积分不足，无法完成需要消耗积分的操作（HTTP 402）。

    Attributes:
        credits_remaining: 当前剩余积分。
        credits_needed: 还差多少积分。
    """

    def __init__(self, message="", status_code=402, response=None,
                 credits_remaining=None, credits_needed=None):
        super().__init__(message, status_code, response)
        self.credits_remaining = credits_remaining
        self.credits_needed = credits_needed


class RateLimitError(RoboPartsError):
    """请求频率超过限制（HTTP 429）。

    Attributes:
        retry_after: 建议的重试等待秒数（来自 Retry-After 头）。
    """

    def __init__(self, message="", status_code=429, response=None, retry_after=None):
        super().__init__(message, status_code, response)
        self.retry_after = retry_after


class NotFoundError(RoboPartsError):
    """请求的资源不存在（HTTP 404）。"""
