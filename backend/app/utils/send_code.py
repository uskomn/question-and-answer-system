import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr

def send_email_verification_code(to_email, code):
    qq_email = "zhu.zhenglin@qq.com"
    auth_code = "zlfaxcomktiubcjd"

    subject = "您的验证码"
    content = f"您的验证码是：{code}，请在5分钟内使用。"

    msg = MIMEText(content, 'plain', 'utf-8')
    msg['From'] = formataddr(("系统管理员", qq_email))
    msg['To'] = to_email
    msg['Subject'] = subject

    server = smtplib.SMTP_SSL("smtp.qq.com", 465)
    server.login(qq_email, auth_code)
    server.sendmail(qq_email, [to_email], msg.as_string())
    server.quit()