package benchmark;

import network.worker.WorkerInterface;
import config.Configuration;
import java.rmi.Naming;
import java.util.ArrayList;
import java.util.List;
import java.io.PrintWriter;
import java.io.FileWriter;

/**
 * Benchmark pour mesurer la latence RMI réelle.
 *
 * Mesure :
 * 1. Temps de Naming.lookup() - résolution du registry
 * 2. Temps d'appel de méthode distante - executeCommand()
 *
 * Méthodologie :
 * - Warmup de 10 itérations (résultats ignorés)
 * - 100 mesures avec statistiques
 * - Intervalles de confiance à 95%
 *
 * @author Distributed Systems Project
 */
public class RMILatencyBenchmark {

    private static final int WARMUP_ITERATIONS = 10;
    private static final int MEASUREMENT_ITERATIONS = 100;

    public static void main(String[] args) throws Exception {
        if (args.length < 1) {
            System.err.println("Usage: RMILatencyBenchmark <worker_host:port> [command] [output_file]");
            System.err.println("  worker_host:port - Worker RMI address (e.g., node1:3000)");
            System.err.println("  command         - Command to execute (default: 'echo test')");
            System.err.println("  output_file     - CSV output file (default: stdout)");
            System.exit(1);
        }

        String workerSpec = args[0];
        String testCommand = args.length > 1 ? args[1] : "echo test";
        String outputFile = args.length > 2 ? args[2] : null;

        String[] parts = workerSpec.split(":");
        String host = parts[0];
        int port = parts.length > 1 ? Integer.parseInt(parts[1]) : 3000;
        String url = Configuration.buildRmiUrl(host, port);

        System.err.println("=== RMI Latency Benchmark ===");
        System.err.println("Worker: " + url);
        System.err.println("Command: " + testCommand);
        System.err.println();

        // === PHASE 1 : WARMUP ===
        System.err.println("Phase 1: Warmup (" + WARMUP_ITERATIONS + " iterations)...");
        for (int i = 0; i < WARMUP_ITERATIONS; i++) {
            try {
                WorkerInterface worker = (WorkerInterface) Naming.lookup(url);
                worker.executeCommand("echo warmup");
            } catch (Exception e) {
                System.err.println("Warmup failed: " + e.getMessage());
                Thread.sleep(500);
            }
        }

        // === PHASE 2 : MESURES ===
        System.err.println("Phase 2: Measuring (" + MEASUREMENT_ITERATIONS + " iterations)...");

        List<Double> lookupTimes = new ArrayList<>();
        List<Double> execTimes = new ArrayList<>();
        List<Double> totalTimes = new ArrayList<>();

        PrintWriter writer = outputFile != null ?
            new PrintWriter(new FileWriter(outputFile)) :
            new PrintWriter(System.out);

        // Header CSV
        writer.println("Iteration,LookupTime_ms,ExecTime_ms,TotalTime_ms");

        for (int i = 0; i < MEASUREMENT_ITERATIONS; i++) {
            try {
                // Mesure du Lookup
                long startLookup = System.nanoTime();
                WorkerInterface worker = (WorkerInterface) Naming.lookup(url);
                long endLookup = System.nanoTime();
                double lookupMs = (endLookup - startLookup) / 1_000_000.0;

                // Mesure de l'exécution distante
                long startExec = System.nanoTime();
                int result = worker.executeCommand(testCommand);
                long endExec = System.nanoTime();
                double execMs = (endExec - startExec) / 1_000_000.0;

                double totalMs = lookupMs + execMs;

                lookupTimes.add(lookupMs);
                execTimes.add(execMs);
                totalTimes.add(totalMs);

                writer.printf("%d,%.3f,%.3f,%.3f%n", i, lookupMs, execMs, totalMs);
                writer.flush();

            } catch (Exception e) {
                System.err.println("Iteration " + i + " failed: " + e.getMessage());
            }
        }

        if (outputFile != null) {
            writer.close();
        }

        // === PHASE 3 : STATISTIQUES ===
        System.err.println();
        System.err.println("=== STATISTICS ===");
        printStatistics("Lookup", lookupTimes);
        printStatistics("Execution", execTimes);
        printStatistics("Total", totalTimes);

        // Résumé JSON pour parsing automatique
        System.err.println();
        System.err.println("=== SUMMARY (JSON) ===");
        System.err.printf("{\"host\":\"%s\",\"lookup_mean\":%.3f,\"exec_mean\":%.3f,\"total_mean\":%.3f}%n",
            host,
            mean(lookupTimes),
            mean(execTimes),
            mean(totalTimes));
    }

    private static void printStatistics(String name, List<Double> values) {
        if (values.isEmpty()) {
            System.err.println(name + ": No data");
            return;
        }

        double mean = mean(values);
        double variance = values.stream()
            .mapToDouble(d -> Math.pow(d - mean, 2))
            .average().orElse(0);
        double stddev = Math.sqrt(variance);
        double min = values.stream().mapToDouble(d -> d).min().orElse(0);
        double max = values.stream().mapToDouble(d -> d).max().orElse(0);
        double median = median(values);

        // Intervalle de confiance à 95% (z = 1.96)
        double ci95 = 1.96 * stddev / Math.sqrt(values.size());

        System.err.println();
        System.err.println("--- " + name + " ---");
        System.err.printf("  N:        %d%n", values.size());
        System.err.printf("  Mean:     %.3f ms%n", mean);
        System.err.printf("  Median:   %.3f ms%n", median);
        System.err.printf("  Std Dev:  %.3f ms%n", stddev);
        System.err.printf("  95%% CI:   [%.3f, %.3f] ms%n", mean - ci95, mean + ci95);
        System.err.printf("  Min:      %.3f ms%n", min);
        System.err.printf("  Max:      %.3f ms%n", max);
        System.err.printf("  CV:       %.1f%%%n", (stddev / mean) * 100);
    }

    private static double mean(List<Double> values) {
        return values.stream().mapToDouble(d -> d).average().orElse(0);
    }

    private static double median(List<Double> values) {
        if (values.isEmpty()) return 0;
        List<Double> sorted = new ArrayList<>(values);
        sorted.sort(Double::compareTo);
        int n = sorted.size();
        if (n % 2 == 0) {
            return (sorted.get(n/2 - 1) + sorted.get(n/2)) / 2.0;
        } else {
            return sorted.get(n/2);
        }
    }
}
