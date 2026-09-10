using Microsoft.AnalysisServices.Tabular;
using System.Text.Json;

if (args.Length == 3 && args[1] == "--manifest")
{
    try
    {
        using var document = JsonDocument.Parse(File.ReadAllText(args[2]));
        var root = document.RootElement;
        var expected = root.GetProperty("tables");
        var parsedDatabase = TmdlSerializer.DeserializeDatabaseFromFolder(args[0]);
        var model = parsedDatabase.Model;
        static void Require(bool condition, string message)
        {
            if (!condition) throw new InvalidDataException(message);
        }
        static string Normalize(string value) => string.Join("\n",
            value.Replace("\r\n", "\n").Trim().Split('\n').Select(line => line.Trim()));
        static bool SameNames(IEnumerable<string> actual, IEnumerable<string> expected) =>
            actual.ToHashSet(StringComparer.Ordinal).SetEquals(expected);
        static DataType ExpectedType(string value) => value switch
        {
            "string" => DataType.String,
            "int64" => DataType.Int64,
            "double" => DataType.Double,
            "decimal" => DataType.Decimal,
            "boolean" => DataType.Boolean,
            "dateTime" => DataType.DateTime,
            _ => throw new InvalidDataException($"unsupported type {value}")
        };
        Require(expected.EnumerateObject().Count() == 5, "manifest must contain five tables");
        Require(parsedDatabase.CompatibilityLevel >= 1400,
            $"grouping metadata requires compatibility level 1400+, got {parsedDatabase.CompatibilityLevel}");
        Require(SameNames(model.Tables.Select(t => t.Name),
            expected.EnumerateObject().Select(t => t.Name)), "unexpected TMDL tables");
        Require(root.GetProperty("relationships").GetArrayLength() == 0 && model.Relationships.Count == 0,
            "relationships are forbidden");
        foreach (var expectedTable in expected.EnumerateObject())
        {
            var table = model.Tables[expectedTable.Name];
            var spec = expectedTable.Value;
            Require(!table.IsHidden, $"{table.Name}: hidden table");
            var columns = spec.GetProperty("columns");
            Require(SameNames(table.Columns.Select(c => c.Name), columns.EnumerateObject().Select(c => c.Name)),
                $"{table.Name}: unexpected columns");
            foreach (var expectedColumn in columns.EnumerateObject())
            {
                var column = table.Columns[expectedColumn.Name];
                var c = expectedColumn.Value;
                Require(column is DataColumn, $"{table.Name}.{column.Name}: expected data column");
                Require(column.DataType == ExpectedType(c.GetProperty("data_type").GetString()!),
                    $"{table.Name}.{column.Name}: data type drift");
                Require(((DataColumn)column).SourceColumn == c.GetProperty("source_column").GetString(),
                    $"{table.Name}.{column.Name}: source column drift");
                Require((column.FormatString ?? "") == c.GetProperty("format_string").GetString()
                    && column.IsHidden == c.GetProperty("hidden").GetBoolean()
                    && column.SummarizeBy == AggregateFunction.None,
                    $"{table.Name}.{column.Name}: presentation drift");
                var expectedGroups = c.GetProperty("group_by_columns")
                    .EnumerateArray().Select(item => item.GetString()!).ToArray();
                var actualGroups = column.RelatedColumnDetails?.GroupByColumns
                    .Select(item => item.GroupingColumn.Name).ToArray() ?? Array.Empty<string>();
                Require(actualGroups.SequenceEqual(expectedGroups),
                    $"{table.Name}.{column.Name}: grouping metadata drift; expected "
                    + $"[{string.Join(", ", expectedGroups)}], got [{string.Join(", ", actualGroups)}]");
            }
            Require(spec.GetProperty("mode").GetString() == "directQuery"
                && table.Partitions.Count == 1, $"{table.Name}: unexpected partitions");
            var partition = table.Partitions[0];
            Require(partition.Name == spec.GetProperty("partition").GetString()
                && partition.Mode == ModeType.DirectQuery && partition.Source is MPartitionSource,
                $"{table.Name}: partition contract drift");
            Require(Normalize(((MPartitionSource)partition.Source).Expression)
                == Normalize(spec.GetProperty("source").GetString()!), $"{table.Name}: source drift");
            var measures = spec.GetProperty("measures");
            Require(SameNames(table.Measures.Select(m => m.Name), measures.EnumerateObject().Select(m => m.Name)),
                $"{table.Name}: unexpected measures");
            foreach (var expectedMeasure in measures.EnumerateObject())
            {
                var measure = table.Measures[expectedMeasure.Name];
                var m = expectedMeasure.Value;
                Require(Normalize(measure.Expression) == Normalize(m.GetProperty("expression").GetString()!),
                    $"{table.Name}.{measure.Name}: expression drift");
                Require((measure.FormatString ?? "") == (m.GetProperty("format_string").GetString() ?? "")
                    && measure.IsHidden == m.GetProperty("hidden").GetBoolean(),
                    $"{table.Name}.{measure.Name}: presentation drift");
                _ = ExpectedType(m.GetProperty("result_type").GetString()!);
            }
        }
        Console.WriteLine(
            $"TMDL deserialized successfully at compatibility level {parsedDatabase.CompatibilityLevel} "
            + "with exact generated model contract; DAX was not executed.");
        return 0;
    }
    catch (Exception error)
    {
        Console.Error.WriteLine($"generated model contract failed: {error.Message}");
        return 1;
    }
}

if (args.Length != 1)
{
    Console.Error.WriteLine("usage: TmdlValidator <TMDL folder>");
    return 2;
}

var database = TmdlSerializer.DeserializeDatabaseFromFolder(args[0]);
var expectedTables = new HashSet<string>
{
    "CaseCommandCenter",
    "ActionOutcomes",
};
var actualTables = database.Model.Tables.Select(table => table.Name).ToHashSet();
if (!actualTables.SetEquals(expectedTables))
{
    Console.Error.WriteLine(
        $"unexpected TMDL tables: {string.Join(", ", actualTables.Order())}"
    );
    return 1;
}

foreach (var table in database.Model.Tables)
{
    if (table.Partitions.Count != 1 || table.Partitions[0].Mode != ModeType.DirectQuery)
    {
        Console.Error.WriteLine($"{table.Name} must have one DirectQuery partition");
        return 1;
    }
}

var expectedMeasures = new Dictionary<string, HashSet<string>>
{
    ["CaseCommandCenter"] = new()
    {
        "Latest Showcase Case",
        "Current Decision ID",
        "Current Decision Status",
        "Revenue At Risk",
        "OTIF Loss %",
        "Scenario Effective Time",
    },
    ["ActionOutcomes"] = new()
    {
        "Action Completion %",
        "Current Action Status",
        "Current Observation Kind",
        "Observed Variance",
        "Projection Refresh Time",
        "Action Scenario Effective Time",
    },
};
foreach (var (tableName, requiredMeasures) in expectedMeasures)
{
    var table = database.Model.Tables[tableName];
    var actualMeasures = table.Measures.Select(measure => measure.Name).ToHashSet();
    if (!requiredMeasures.IsSubsetOf(actualMeasures))
    {
        var missing = requiredMeasures.Except(actualMeasures).Order();
        Console.Error.WriteLine($"{tableName} missing measures: {string.Join(", ", missing)}");
        return 1;
    }
}

var varianceExpression = database.Model.Tables["ActionOutcomes"]
    .Measures["Observed Variance"]
    .Expression;
if (
    varianceExpression.Contains("ALL(ActionOutcomes)", StringComparison.OrdinalIgnoreCase)
    || varianceExpression.Contains("AVERAGEX", StringComparison.OrdinalIgnoreCase)
    || varianceExpression.Contains("REMOVEFILTERS", StringComparison.OrdinalIgnoreCase)
    || !varianceExpression.Contains("[Current Decision ID]", StringComparison.Ordinal)
    || !varianceExpression.Contains("ActionOutcomes[decision_id] = DecisionId", StringComparison.Ordinal)
    || !varianceExpression.Contains("IFERROR(VALUE(PredictedText), BLANK())", StringComparison.Ordinal)
    || !varianceExpression.Contains("IFERROR(VALUE(ObservedText), BLANK())", StringComparison.Ordinal)
)
{
    Console.Error.WriteLine("Observed Variance does not satisfy the safe per-metric contract");
    return 1;
}

Console.WriteLine("TMDL deserialized successfully with Microsoft.AnalysisServices.");
return 0;
