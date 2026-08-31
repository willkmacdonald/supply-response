using Microsoft.AnalysisServices.Tabular;

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
        "Revenue At Risk",
        "OTIF Loss %",
        "Scenario Effective Time",
    },
    ["ActionOutcomes"] = new()
    {
        "Action Completion %",
        "Observed Variance",
        "Projection Refresh Time",
        "Scenario Effective Time",
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
