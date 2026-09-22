$ErrorActionPreference = "Stop"

docker exec traffic-ai-postgres psql -U traffic_admin -d traffic_ai_db -c "SELECT version(), current_database(), current_user;"
docker exec traffic-ai-postgres psql -U traffic_admin -d traffic_ai_db -c "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name;"
