from app import create_app

app = create_app()

# poetry run flask:
#   --app app:create_app --debug run
# up:
# 	docker compose --env-file .env.docker up -d
# down:
# 	docker compose down
# logs:
# 	docker compose logs -f --tail=100
# nuke:
# 	docker compose down -v  # WARNING: deletes DB/Redis/S3 data
