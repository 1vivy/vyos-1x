<!-- include start from bgp-afi-redistribute-metric-route-map.xml.i -->
<leafNode name="metric">
  <properties>
    <help>Metric for redistributed routes</help>
    <valueHelp>
      <format>u32:1-4294967295</format>
      <description>Metric for redistributed routes</description>
    </valueHelp>
  </properties>
</leafNode>
<leafNode name="route-map">
  <properties>
    <help>Route map to filter redistributed routes</help>
    <completionHelp>
      <path>policy route-map</path>
    </completionHelp>
  </properties>
</leafNode>
<!-- include end -->
