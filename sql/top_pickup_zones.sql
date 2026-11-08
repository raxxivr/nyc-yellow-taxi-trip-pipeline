-- Question: Which pickup zones had the most trips? (one row per pickup zone, top 10)
SELECT 
	pickup_location_id,
	pickup_borough,
	COALESCE(pickup_zone, 'Unknown (264)') AS zone_label,
	COUNT(*) AS trip_count,
  ROUND((COUNT(*) * 100.0) / SUM(COUNT(*)) OVER (), 2) AS pct_of_total
FROM clean.trips
GROUP BY 
	pickup_location_id, 
	pickup_borough, 
	pickup_zone
ORDER BY trip_count DESC
LIMIT 10;