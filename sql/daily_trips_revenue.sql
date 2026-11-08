-- Question: How many trips and how much revenue per day in September 2026? (one row per pickup date)
SELECT 
	pickup_datetime::DATE AS trip_date,
	COUNT(*) AS trip_count,
	SUM(total_amount) AS gross_revenue,
	SUM(fare_amount) AS fare_revenue,
	SUM(tip_amount) AS tip_revenue
FROM clean.trips
WHERE pickup_datetime >= '2026-09-01' AND pickup_datetime < '2026-10-01'
GROUP BY pickup_datetime::DATE
ORDER BY trip_date;