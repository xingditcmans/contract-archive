@echo off
chcp 65001 >nul
echo.
echo  重置管理员密码脚本
echo  =========================
echo.
echo  此脚本会将 admin 账号密码重置为: admin123
echo  首次使用后请立即登录并修改密码！
echo.
pause

docker exec -it contract-backend python -c "
import sys
sys.path.append('/app')
from passlib.context import CryptContext
pwd_ctx = CryptContext(schemes=['argon2'], deprecated='auto')
print('新密码哈希:', pwd_ctx.hash('admin123'))
"

echo.
echo 请将上述哈希值复制到数据库中，或联系开发者执行重置。
echo.
pause
