<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor version="1.0.0" xmlns="http://www.opengis.net/sld" xmlns:ogc="http://www.opengis.net/ogc"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://www.opengis.net/sld http://schemas.opengis.net/sld/1.0.0/StyledLayerDescriptor.xsd">
  <NamedLayer>
    <Name>rcd_barrios</Name>
    <UserStyle>
      <Title>Barrios</Title>
      <FeatureTypeStyle>
        <Rule>
          <PolygonSymbolizer>
            <Stroke><CssParameter name="stroke">#6c757d</CssParameter><CssParameter name="stroke-width">0.6</CssParameter></Stroke>
          </PolygonSymbolizer>
        </Rule>
        <Rule>
          <MaxScaleDenominator>20000</MaxScaleDenominator>   <!-- nombres solo al acercarse -->
          <TextSymbolizer>
            <Label><ogc:PropertyName>nombre</ogc:PropertyName></Label>
            <Font><CssParameter name="font-family">SansSerif</CssParameter><CssParameter name="font-size">10</CssParameter></Font>
            <Halo><Radius>1.5</Radius><Fill><CssParameter name="fill">#ffffff</CssParameter></Fill></Halo>
            <Fill><CssParameter name="fill">#495057</CssParameter></Fill>
          </TextSymbolizer>
        </Rule>
      </FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>
