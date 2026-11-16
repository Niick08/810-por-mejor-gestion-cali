<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor version="1.0.0" xmlns="http://www.opengis.net/sld" xmlns:ogc="http://www.opengis.net/ogc"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://www.opengis.net/sld http://schemas.opengis.net/sld/1.0.0/StyledLayerDescriptor.xsd">
  <NamedLayer>
    <Name>rcd_comunas</Name>
    <UserStyle>
      <Title>Comunas</Title>
      <FeatureTypeStyle>
        <Rule>
          <PolygonSymbolizer>
            <Stroke><CssParameter name="stroke">#1f3a5f</CssParameter><CssParameter name="stroke-width">2</CssParameter>
              <CssParameter name="stroke-dasharray">6 3</CssParameter></Stroke>
          </PolygonSymbolizer>
          <TextSymbolizer>
            <Label><ogc:PropertyName>nombre</ogc:PropertyName></Label>
            <Font><CssParameter name="font-family">SansSerif</CssParameter><CssParameter name="font-size">12</CssParameter>
              <CssParameter name="font-weight">bold</CssParameter></Font>
            <Halo><Radius>2</Radius><Fill><CssParameter name="fill">#ffffff</CssParameter></Fill></Halo>
            <Fill><CssParameter name="fill">#1f3a5f</CssParameter></Fill>
          </TextSymbolizer>
        </Rule>
      </FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>
