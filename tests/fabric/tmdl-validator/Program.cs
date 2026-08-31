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

Console.WriteLine("TMDL deserialized successfully with Microsoft.AnalysisServices.");
return 0;
