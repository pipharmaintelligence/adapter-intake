<?php

// Offline metadata normalization only: no Laravel bootstrap, .env, DB or catalog writes.
use App\Observability\InnovationLab\Services\AssetIdentityResolver;
use App\Observability\InnovationLab\Services\AssetManifestRegistry;
use App\Observability\InnovationLab\Services\PublishedAssetManifestRegistry;

if ($argc !== 5) {
    throw new RuntimeException('Expected Assets source, temporary manifest, key and version.');
}
[, $source, $manifest, $key, $version] = $argv;
require $source.'/vendor/autoload.php';

$registry = new AssetManifestRegistry(dirname($manifest));
// Explicit paths and injected allowlist avoid app configuration and published catalog reads.
$published = new PublishedAssetManifestRegistry($registry, dirname($manifest).'/unused-catalog.json');
$resolver = new AssetIdentityResolver($registry->manifests(), $published);
$skills = $resolver->skillDependencies($key, $version);

$rejections = [];
foreach (['launch', 'resume'] as $mode) {
    try {
        $resolver->resolve($key, $version, $mode);
        throw new LogicException('Draft unexpectedly resolved.');
    } catch (RuntimeException $exception) {
        if (! str_contains($exception->getMessage(), 'state [draft]')) {
            throw $exception;
        }
        $rejections[$mode.'_rejected'] = true;
    }
}
echo json_encode(['status' => 'normalized_draft', 'skills' => $skills, ...$rejections], JSON_THROW_ON_ERROR).PHP_EOL;
