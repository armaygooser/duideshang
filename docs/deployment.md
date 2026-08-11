# 部署说明

项目采用同一代码仓库、两个 Vercel Project：一个部署 FastAPI，一个部署 Next.js。先部署后端，再把后端地址写入前端环境变量。

## 1. FastAPI 后端

Vercel Project Root Directory 设为 `apps/api`，Framework Preset 设为 FastAPI。Vercel 通过根目录 `main.py` 发现应用，实际实现仍位于 `app/main.py`；依赖声明在 `pyproject.toml`，行业规则随 `apps/api/knowledge` 一起部署。

```text
Framework: FastAPI (自动识别)
Build Command: 留空
Output Directory: 留空
```

首次部署使用本地演示 Provider 即可，不需要任何密钥：

```text
MODEL_PROVIDER=local-demo
CORS_ORIGINS=https://<frontend-domain>
```

健康检查路径为 `/health`。若暂时还不知道前端域名，可先完成后端部署，获得前端域名后更新 `CORS_ORIGINS` 并重新部署。

## 2. Vercel 前端

1. 导入同一仓库，将 Root Directory 设为 `apps/web`。
2. Framework Preset 选择 Next.js。
3. 设置 `NEXT_PUBLIC_API_BASE_URL=https://<api-domain>`。
4. 执行生产构建并检查 `/health`、需求分析、逐项确认和正式报价。

## 3. 当前生产地址

- 前端：<https://duideshang-demo.vercel.app>
- 后端：<https://duideshang-api.vercel.app>
- 健康检查：<https://duideshang-api.vercel.app/health>

两个 Project 的 SSO Deployment Protection 已关闭，持有链接的面试官无需 Vercel 登录即可访问。以下非敏感变量已持久化到 Production 环境：

- `duideshang-demo`: `NEXT_PUBLIC_API_BASE_URL=https://duideshang-api.vercel.app`
- `duideshang-api`: `MODEL_PROVIDER=local-demo`
- `duideshang-api`: `CORS_ORIGINS=https://duideshang-demo.vercel.app`

## 4. 生产验证

- 打开后端 `/health`，确认 `status=ok` 且 `active_provider=local-demo`。
- 打开前端，确认右上角显示本地演示模式，而不是服务不可用。
- 运行“标准门头询价”，完成预设确认并生成确定性报价。
- 刷新页面后确认 localStorage 会话可以恢复。
- 用移动端尺寸检查三栏布局是否正确降级。
- 不要在浏览器控制台、网络响应或 Git 仓库中出现任何 API Key。

## 发布前清单

- 由具体门店审核并替换全部演示价目、材料规格、施工规则和验收模板。
- 使用 HTTPS；限制 CORS 到正式前端域名。
- 决定持久化、身份、审计、备份与数据保留方案；不要把客户对话作为无主数据长期保存。
- 将 `MODEL_PROVIDER=deepseek`、`DEEPSEEK_API_KEY`、`DEEPSEEK_MODEL=deepseek-v4-flash` 放入后端 Secret，禁止使用 `NEXT_PUBLIC_*` 暴露密钥；当前实现包含超时、自动降级和 Pydantic 输出校验，正式发布仍需增加调用审计和费用告警。
- 增加真实域名下的端到端测试、错误监控和依赖安全扫描。
- 评估个人信息处理、客户授权、报价法律效力和电子确认留痕要求。
