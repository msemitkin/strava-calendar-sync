.PHONY: init deploy configure destroy

init:
	terraform -chdir=terraform init

deploy:
	terraform -chdir=terraform apply

configure:
	python3 scripts/configure.py

destroy:
	terraform -chdir=terraform destroy

