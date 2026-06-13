.PHONY: install demo test run job docker zip clean

install:
	pip install -r requirements.txt

demo:
	python -m cli.demo

test:
	python -m pytest -q

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

job:
	python -m app.jobs

docker:
	docker compose up --build

clean:
	rm -f cilantro.db config/calibration_local.yaml
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
