ARG BASE_IMAGE=lab/lab-sim-base:latest
FROM ${BASE_IMAGE}
COPY services/robot_sim /app/robot_sim
CMD ["python", "/app/robot_sim/sim.py"]
