-- 0003_warm_paths: team-wide warm introduction paths over the graph.
--
-- Starts from every internal team member and walks live knows / co_occurs /
-- introduced edges (in either direction) for up to p_max_hops hops. A path's
-- score is the product of edge strengths along it. The target may be a person,
-- or a company (any live works_at employee counts as reaching it).
-- Runs as the caller, so row-level security confines it to one tenant.

CREATE FUNCTION warm_paths(p_target uuid, p_max_hops int DEFAULT 3, p_limit int DEFAULT 10)
RETURNS TABLE (path uuid[], score double precision, hops int, edge_types text[])
LANGUAGE sql STABLE AS $$
WITH RECURSIVE
targets AS (
    SELECT p_target AS id
    UNION
    SELECT e.src_id FROM edges e
     WHERE e.dst_id = p_target AND e.type = 'works_at' AND e.valid_to IS NULL
),
g AS (
    SELECT src_id AS a, dst_id AS b, type, coalesce((props->>'strength')::float, confidence) AS w
      FROM edges WHERE valid_to IS NULL AND type IN ('knows', 'co_occurs', 'introduced')
    UNION ALL
    SELECT dst_id, src_id, type, coalesce((props->>'strength')::float, confidence)
      FROM edges WHERE valid_to IS NULL AND type IN ('knows', 'co_occurs', 'introduced')
),
strong AS (SELECT * FROM g WHERE w >= 0.05),
walk AS (
    SELECT s.b AS node, ARRAY[s.a, s.b] AS path, s.w AS score, 1 AS hops, ARRAY[s.type] AS types
      FROM strong s JOIN people p ON p.id = s.a AND p.is_internal
    UNION ALL
    SELECT s.b, w.path || s.b, w.score * s.w, w.hops + 1, w.types || s.type
      FROM walk w JOIN strong s ON s.a = w.node
     WHERE w.hops < p_max_hops
       AND NOT s.b = ANY (w.path)
       AND w.node NOT IN (SELECT id FROM targets)
       -- Paths go out through one team member; they don't hop back inside.
       AND NOT EXISTS (SELECT 1 FROM people ip WHERE ip.id = s.b AND ip.is_internal)
)
SELECT path, score, hops, types
  FROM walk
 WHERE node IN (SELECT id FROM targets)
 ORDER BY score DESC, hops
 LIMIT p_limit
$$;
