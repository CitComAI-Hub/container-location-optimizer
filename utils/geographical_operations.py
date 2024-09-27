import math
from shapely import to_geojson, voronoi_polygons, intersection, MultiPoint


# Haversine function
def haversine(coord1, coord2):
    # Radius of the Earth in meters
    R = 6371000
    lon1, lat1 = map(math.radians, coord1)
    lon2, lat2 = map(math.radians, coord2)

    dlon = lon2 - lon1
    dlat = math.radians(coord2[1] - coord1[1])

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = R * c
    return distance


# Function to convert geographic coordinates to a grid index
def to_grid_index(coord, cell_size=50):
    R = 6371000  # Earth radius in meters

    # Convert degrees to radians
    lon, lat = coord
    lat_radians = math.radians(lat)

    # Latitude and longitude distance to meters
    lat_cell_size = cell_size / R * (180 / math.pi)
    lon_cell_size = cell_size / (R * math.cos(lat_radians)) * (180 / math.pi)

    # Compute grid indices based on cell size
    lat_index = int(lat / lat_cell_size)
    lon_index = int(lon / lon_cell_size)

    return (lat_index, lon_index)


# Optimized function to remove similar containers
def remove_similar_containers(containers, threshold=50):
    grid = {}
    filtered_containers = []

    for container in containers:
        # Extract the coordinates of the current container
        coord = container["location"]["value"]["coordinates"]

        # Get grid index of the current container
        grid_index = to_grid_index(coord, threshold)

        # Check neighbors and current grid cell
        is_similar = False
        nearby_cells = [
            (grid_index[0] + dx, grid_index[1] + dy)
            for dx in [-1, 0, 1]
            for dy in [-1, 0, 1]
        ]

        # Iterate over this and neighboring cells
        for cell in nearby_cells:
            if cell in grid:
                for nearby_container in grid[cell]:
                    nearby_coord = nearby_container["location"]["value"]["coordinates"]
                    distance = haversine(coord, nearby_coord)

                    # If within the threshold, mark as similar
                    if distance < threshold:
                        is_similar = True
                        break
            if is_similar:
                break

        # If no similar container found, add to the grid and filtered list
        if not is_similar:
            if grid_index not in grid:
                grid[grid_index] = []
            grid[grid_index].append(container)
            filtered_containers.append(container)

    return filtered_containers


def get_solution_coords(solution_vector, possible_locations):
    """
    Converts solution representation into a list of [long,lat] locations

    :param list solution_vector: Solution / individual list
    :param list possible_locations: Locations in [lon, lat] format
    """
    points = []
    for i, container in enumerate(possible_locations):
        if solution_vector[i] == 1:
            points.append(container["location"]["value"]["coordinates"])
    return points


def voronoi_division(points, bound_polygon):
    # Generate voronoi polygons
    voronoi = voronoi_polygons(MultiPoint(points), extend_to=bound_polygon)

    # Intersect generated polygons with Valencia region
    voronoi_intersected = []
    for i, polygon in enumerate(voronoi.geoms):
        if not polygon.is_empty:
            intersect = intersection(polygon, bound_polygon)
            voronoi_intersected.append(to_geojson(intersect))
    return voronoi_intersected
