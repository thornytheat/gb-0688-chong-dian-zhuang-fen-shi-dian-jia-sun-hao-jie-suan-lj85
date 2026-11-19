# 运行维护

主服务端口与Compose保持一致。数据保存在records命名卷，应用代码不需要写入权限。

```sh
docker compose logs --tail=80 app
docker compose restart app
docker compose exec -T app pytest -q
docker compose down --remove-orphans
```

健康检查GET /health。失败输入返回原因码，结构性错误422，过大文件413，陈旧复核409。补读失败返回422原因码REREAD且不落新记录。
文件内容最大4MB。批次先计算再原子保存，失败不留半条记录。补读`POST /api/reread/<run_id>`先完整核算再落账，相同内容重试返回同一批次（reread.status=reused）；旧批次与已复核记录始终原样保留。证据CSV按原始行号定位。
