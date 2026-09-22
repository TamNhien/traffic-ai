$ErrorActionPreference = "Stop"

Write-Host "[Traffic AI] PostgreSQL identity" -ForegroundColor Cyan
docker exec traffic-ai-postgres psql -U traffic_admin -d traffic_ai_db -c "SELECT version(), current_database(), current_user;"

Write-Host "`n[Traffic AI] Alembic revision" -ForegroundColor Cyan
docker exec traffic-ai-postgres psql -U traffic_admin -d traffic_ai_db -c "SELECT version_num FROM alembic_version;"

Write-Host "`n[Traffic AI] Application schema version" -ForegroundColor Cyan
docker exec traffic-ai-postgres psql -U traffic_admin -d traffic_ai_db -c "SELECT key, value FROM system_settings WHERE key='schema_version';"

Write-Host "`n[Traffic AI] Tables" -ForegroundColor Cyan
docker exec traffic-ai-postgres psql -U traffic_admin -d traffic_ai_db -c "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name;"

Write-Host "`n[Traffic AI] Camera AI columns" -ForegroundColor Cyan
docker exec traffic-ai-postgres psql -U traffic_admin -d traffic_ai_db -c "SELECT column_name, data_type FROM information_schema.columns WHERE table_name='cameras' AND column_name IN ('confidence_threshold','line_x1','line_y1','line_x2','line_y2') ORDER BY ordinal_position;"

Write-Host "`n[Traffic AI] Active AI model" -ForegroundColor Cyan
docker exec traffic-ai-postgres psql -U traffic_admin -d traffic_ai_db -c "SELECT id, name, version, architecture, model_path, is_active FROM ai_models ORDER BY is_active DESC, id DESC;"

Write-Host "`n[Traffic AI] Camera sources" -ForegroundColor Cyan
docker exec traffic-ai-postgres psql -U traffic_admin -d traffic_ai_db -c "SELECT id, code, name, source_type, source_url, status FROM cameras ORDER BY id;"
