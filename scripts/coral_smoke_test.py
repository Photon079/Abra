import asyncio
from app.coral.query import coral_query_service

strava_sql = "SELECT sum(distance)/1000 AS total_km, sum(moving_time)/3600.0 AS total_hours, avg(average_speed) as avg_speed FROM strava.activities WHERE type = 'Run' AND start_date_local >= date('now', '-30 day')"
print("Strava:", coral_query_service.run_query(strava_sql))

chess_sql = "SELECT white__result, black__result FROM chesscom.games"
print("Chess:", coral_query_service.run_query(chess_sql))
