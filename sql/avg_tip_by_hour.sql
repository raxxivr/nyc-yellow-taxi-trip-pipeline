-- Question: What is the average card tip by pickup hour? (one row per pickup hour)
SELECT 
	EXTRACT(HOUR FROM pickup_datetime) AS pickup_hour,
	COUNT(*) AS card_trips,
	AVG(tip_amount) AS avg_tip,
	PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY tip_amount) AS median_tip
FROM clean.trips
WHERE payment_type = 1
GROUP BY EXTRACT(HOUR FROM pickup_datetime)
ORDER BY pickup_hour;