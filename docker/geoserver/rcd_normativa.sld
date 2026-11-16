<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor version="1.0.0" xmlns="http://www.opengis.net/sld" xmlns:ogc="http://www.opengis.net/ogc"
  xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://www.opengis.net/sld http://schemas.opengis.net/sld/1.0.0/StyledLayerDescriptor.xsd">
  <NamedLayer>
    <Name>rcd_normativa</Name>
    <UserStyle>
      <Title>Capa normativa RCD</Title>
      <FeatureTypeStyle>
        <!-- Dónde SÍ: receptores inscritos y vigentes -->
        <Rule>
          <Title>Receptor inscrito</Title>
          <ogc:Filter><ogc:PropertyIsEqualTo><ogc:PropertyName>capa</ogc:PropertyName><ogc:Literal>receptor</ogc:Literal></ogc:PropertyIsEqualTo></ogc:Filter>
          <PolygonSymbolizer>
            <Fill><CssParameter name="fill">#1f7a4d</CssParameter><CssParameter name="fill-opacity">0.35</CssParameter></Fill>
            <Stroke><CssParameter name="stroke">#1f7a4d</CssParameter><CssParameter name="stroke-width">2</CssParameter></Stroke>
          </PolygonSymbolizer>
        </Rule>
        <!-- Dónde NO: agua (ríos, quebradas, canales, humedales y sus rondas) -->
        <Rule>
          <Title>Zona prohibida: agua y rondas</Title>
          <ogc:Filter><ogc:And>
            <ogc:PropertyIsEqualTo><ogc:PropertyName>capa</ogc:PropertyName><ogc:Literal>prohibida</ogc:Literal></ogc:PropertyIsEqualTo>
            <ogc:Or>
              <ogc:PropertyIsEqualTo><ogc:PropertyName>tipo</ogc:PropertyName><ogc:Literal>rio</ogc:Literal></ogc:PropertyIsEqualTo>
              <ogc:PropertyIsEqualTo><ogc:PropertyName>tipo</ogc:PropertyName><ogc:Literal>quebrada</ogc:Literal></ogc:PropertyIsEqualTo>
              <ogc:PropertyIsEqualTo><ogc:PropertyName>tipo</ogc:PropertyName><ogc:Literal>canal</ogc:Literal></ogc:PropertyIsEqualTo>
              <ogc:PropertyIsEqualTo><ogc:PropertyName>tipo</ogc:PropertyName><ogc:Literal>humedal</ogc:Literal></ogc:PropertyIsEqualTo>
            </ogc:Or>
          </ogc:And></ogc:Filter>
          <PolygonSymbolizer>
            <Fill><CssParameter name="fill">#b42318</CssParameter><CssParameter name="fill-opacity">0.45</CssParameter></Fill>
            <Stroke><CssParameter name="stroke">#8e1b10</CssParameter><CssParameter name="stroke-width">0.6</CssParameter></Stroke>
          </PolygonSymbolizer>
        </Rule>
        <!-- Dónde NO: parques, zonas verdes y demás -->
        <Rule>
          <Title>Zona prohibida: parques y zonas verdes</Title>
          <ogc:Filter><ogc:And>
            <ogc:PropertyIsEqualTo><ogc:PropertyName>capa</ogc:PropertyName><ogc:Literal>prohibida</ogc:Literal></ogc:PropertyIsEqualTo>
            <ogc:Not><ogc:Or>
              <ogc:PropertyIsEqualTo><ogc:PropertyName>tipo</ogc:PropertyName><ogc:Literal>rio</ogc:Literal></ogc:PropertyIsEqualTo>
              <ogc:PropertyIsEqualTo><ogc:PropertyName>tipo</ogc:PropertyName><ogc:Literal>quebrada</ogc:Literal></ogc:PropertyIsEqualTo>
              <ogc:PropertyIsEqualTo><ogc:PropertyName>tipo</ogc:PropertyName><ogc:Literal>canal</ogc:Literal></ogc:PropertyIsEqualTo>
              <ogc:PropertyIsEqualTo><ogc:PropertyName>tipo</ogc:PropertyName><ogc:Literal>humedal</ogc:Literal></ogc:PropertyIsEqualTo>
            </ogc:Or></ogc:Not>
          </ogc:And></ogc:Filter>
          <PolygonSymbolizer>
            <Fill><CssParameter name="fill">#e8590c</CssParameter><CssParameter name="fill-opacity">0.35</CssParameter></Fill>
            <Stroke><CssParameter name="stroke">#b34700</CssParameter><CssParameter name="stroke-width">0.5</CssParameter></Stroke>
          </PolygonSymbolizer>
        </Rule>
      </FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>
