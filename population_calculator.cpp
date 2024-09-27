#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <gdal_priv.h>
#include <ogr_geometry.h>
#include <json/json.h>
#include <vector>
#include <iostream>
#include <sstream>

// Function to create an OGRPolygon from GeoJSON coordinates
OGRPolygon* createPolygonFromCoordinates(const Json::Value& coordinates) {
    OGRPolygon* polygon = new OGRPolygon();
    OGRLinearRing ring;

    for (const auto& coord : coordinates) {
        ring.addPoint(coord[0].asDouble(), coord[1].asDouble());
    }

    ring.closeRings(); // Ensure the ring is closed
    polygon->addRing(&ring);
    return polygon;
}

// Function to parse a Polygon GeoJSON
OGRGeometry* parsePolygonGeoJSON(const Json::Value& root) {
    const Json::Value& coordinates = root["coordinates"];
    if (coordinates.isArray() && coordinates.size() > 0) {
        return createPolygonFromCoordinates(coordinates[0]);
    } else {
        std::cerr << "Invalid Polygon coordinates format." << std::endl;
        return nullptr;
    }
}

// Function to parse a MultiPolygon GeoJSON
OGRGeometryCollection* parseMultiPolygonGeoJSON(const Json::Value& root) {
    OGRGeometryCollection* multiPolygon = new OGRGeometryCollection();
    const Json::Value& coordinates = root["coordinates"];

    for (const auto& polygonCoords : coordinates) {
        OGRPolygon* polygon = createPolygonFromCoordinates(polygonCoords[0]);
        multiPolygon->addGeometry(polygon);
    }

    return multiPolygon;
}

// Function to parse GeoJSON and return an OGRGeometry object
OGRGeometry* parseGeoJSON(const std::string& geojson) {
    Json::CharReaderBuilder rbuilder;
    std::string errs;
    Json::Value root;
    std::istringstream s(geojson);
    if (!Json::parseFromStream(rbuilder, s, &root, &errs)) {
        std::cerr << "Failed to parse GeoJSON: " << errs << std::endl;
        return nullptr;
    }

    std::string type = root["type"].asString();
    if (type == "Polygon") {
        return parsePolygonGeoJSON(root);
    } else if (type == "MultiPolygon") {
        return parseMultiPolygonGeoJSON(root);
    } else {
        std::cerr << "Unsupported GeoJSON geometry type: " << type << std::endl;
        return nullptr;
    }
}

// Function to get the bounding box of the geometry
void getBoundingBox(OGRGeometry* geom, double* minX, double* maxX, double* minY, double* maxY) {
    OGREnvelope envelope;
    geom->getEnvelope(&envelope);
    *minX = envelope.MinX;
    *maxX = envelope.MaxX;
    *minY = envelope.MinY;
    *maxY = envelope.MaxY;
}

// Function to check if two bounding boxes overlap
bool doBoundingBoxesOverlap(double minX1, double maxX1, double minY1, double maxY1, double minX2, double maxX2, double minY2, double maxY2) {
    return !(minX1 > maxX2 || maxX1 < minX2 || minY1 > maxY2 || maxY1 < minY2);
}

// Function to calculate population inside the geometry
double calculatePopulation(OGRGeometry* geometry, const std::string& rasterFilePath) {
    const int NO_DATA_VALUE = -200; // Define NoData value

    if (geometry == nullptr) {
        std::cerr << "Invalid geometry." << std::endl;
        return -1.0;
    }

    GDALAllRegister();
    GDALDataset* poDataset = (GDALDataset*)GDALOpen(rasterFilePath.c_str(), GA_ReadOnly);
    if (poDataset == nullptr) {
        std::cerr << "Failed to open raster file." << std::endl;
        return -1.0;
    }

    GDALRasterBand* poBand = poDataset->GetRasterBand(1);
    int nXSize = poBand->GetXSize();
    int nYSize = poBand->GetYSize();

    double adfGeoTransform[6];
    poDataset->GetGeoTransform(adfGeoTransform);

    double rasterMinX = adfGeoTransform[0];
    double rasterMaxX = adfGeoTransform[0] + nXSize * adfGeoTransform[1];
    double rasterMinY = adfGeoTransform[3] + nYSize * adfGeoTransform[5];
    double rasterMaxY = adfGeoTransform[3];

    double geomMinX, geomMaxX, geomMinY, geomMaxY;
    getBoundingBox(geometry, &geomMinX, &geomMaxX, &geomMinY, &geomMaxY);

    if (!doBoundingBoxesOverlap(geomMinX, geomMaxX, geomMinY, geomMaxY, rasterMinX, rasterMaxX, rasterMinY, rasterMaxY)) {
        std::cerr << "GeoJSON does not overlap with the raster." << std::endl;
        GDALClose((GDALDatasetH)poDataset);
        return -1.0;
    }

    int xStart = static_cast<int>((geomMinX - adfGeoTransform[0]) / adfGeoTransform[1]);
    int xEnd = static_cast<int>((geomMaxX - adfGeoTransform[0]) / adfGeoTransform[1]);
    int yStart = static_cast<int>((geomMaxY - adfGeoTransform[3]) / adfGeoTransform[5]);
    int yEnd = static_cast<int>((geomMinY - adfGeoTransform[3]) / adfGeoTransform[5]);

    xStart = std::max(0, xStart);
    xEnd = std::min(nXSize - 1, xEnd);
    yStart = std::max(0, yStart);
    yEnd = std::min(nYSize - 1, yEnd);

    double population = 0.0;

    // Pre-calculate the geotransform coefficients
    const double gt0 = adfGeoTransform[0];
    const double gt1 = adfGeoTransform[1];
    const double gt2 = adfGeoTransform[2];
    const double gt3 = adfGeoTransform[3];
    const double gt4 = adfGeoTransform[4];
    const double gt5 = adfGeoTransform[5];

    // Read the raster block in larger chunks to minimize I/O operations
    const int chunkSize = 256; // Adjust as necessary for your system
    std::vector<int> rasterBlock(chunkSize * chunkSize);

    // Iterate over the pixels in the specified area
    for (int y = yStart; y <= yEnd; y += chunkSize) {
        int yChunkSize = std::min(chunkSize, yEnd - y + 1);

        for (int x = xStart; x <= xEnd; x += chunkSize) {
            int xChunkSize = std::min(chunkSize, xEnd - x + 1);

            poBand->RasterIO(GF_Read, x, y, xChunkSize, yChunkSize, rasterBlock.data(),
                             xChunkSize, yChunkSize, GDT_Int32, 0, 0);

            for (int i = 0; i < yChunkSize; ++i) {
                for (int j = 0; j < xChunkSize; ++j) {
                    int pixelValue = rasterBlock[i * xChunkSize + j];
                    if (pixelValue == NO_DATA_VALUE) {
                        continue; // Skip NoData values
                    }

                    double lon = gt0 + (x + j) * gt1 + (y + i) * gt2;
                    double lat = gt3 + (x + j) * gt4 + (y + i) * gt5;

                    OGRPoint point(lon, lat);
                    if (geometry->Contains(&point)) {
                        population += pixelValue;
                    }
                }
            }
        }
    }

    GDALClose((GDALDatasetH)poDataset);
    return population;
}

// Python binding
namespace py = pybind11;

double calculate_population_py(const std::string& geojson, const std::string& rasterFilePath) {
    OGRGeometry* geometry = parseGeoJSON(geojson);
    if (geometry == nullptr) {
        throw std::runtime_error("Failed to parse GeoJSON.");
    }

    double population = calculatePopulation(geometry, rasterFilePath);
    OGRGeometryFactory::destroyGeometry(geometry);
    return population;
}

PYBIND11_MODULE(population_calculator, m) {
    m.def("calculate_population", &calculate_population_py, "Calculate population inside a geometry from GeoJSON",
          py::arg("geojson"), py::arg("rasterFilePath"));
}
