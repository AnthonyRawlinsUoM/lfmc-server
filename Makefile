all: build install pull

build:
	@docker build --tag=anthonyrawlinsuom/lfmc-api .
	
install:
	@docker push anthonyrawlinsuom/lfmc-api
	
pull:
	@docker pull anthonyrawlinsuom/lfmc-api
	
release:
	./release.sh

clean:
	@docker rmi --force anthonyrawlinsuom/lfmc-api