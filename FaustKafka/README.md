# Pub-Sub Capability Added
## app = faust.App("agent_pipeline", broker="kafka://localhost:9092")
## run docker to spin up redpanda 
docker run -d --name=redpanda   -p 9092:9092 -p 9644:9644   redpandadata/redpanda:latest   redpanda start   --overprovisioned   --smp 1   --memory 1G   --reserve-memory 0M   --node-id 0   --check=false   --kafka-addr PLAINTEXT://0.0.0.0:9092   --advertise-kafka-addr PLAINTEXT://localhost:9092

## to launch program python agent.py worker -l info