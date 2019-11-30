const fs = require("fs");
const path = require("path");
const Config = require("./config");

class ModelManager {
    get_models() {
        return new Promise((resolve, reject) => {
            fs.readdir(Config.MODEL_DIRECTORY, (error, models) => {
                if (error) {
                    reject(error);
                } else {
                    const promises = [];
                    models.forEach(model => {
                        const model_path = path.join(
                            Config.MODEL_DIRECTORY,
                            model,
                            "predictions"
                        );
                        promises.push(
                            new Promise((resolve_, reject_) => {
                                return fs.readdir(
                                    model_path,
                                    (err, filenames) => {
                                        if (!err && filenames.length > 0) {
                                            const model_split = model.split(
                                                "-"
                                            );
                                            const test_predictions_filenames = filenames.filter(
                                                filename =>
                                                    filename.includes("test")
                                            );
                                            const validation_predictions_filenames = filenames.filter(
                                                filename =>
                                                    filename.includes(
                                                        "validation"
                                                    )
                                            );
                                            resolve_({
                                                model_name: model_split[0],
                                                model_directory: model,
                                                input_size: parseInt(
                                                    model_split[1]
                                                        .split("_")
                                                        .slice(-1)
                                                        .pop()
                                                ),
                                                learning_rate: parseFloat(
                                                    model_split[2]
                                                        .split("_")
                                                        .slice(-1)
                                                        .pop()
                                                ),
                                                batch_size: parseInt(
                                                    model_split[3]
                                                        .split("_")
                                                        .slice(-1)
                                                        .pop()
                                                ),
                                                predictions: {
                                                    test: test_predictions_filenames,
                                                    validation: validation_predictions_filenames,
                                                },
                                            });
                                        } else {
                                            resolve_(null);
                                        }
                                    }
                                );
                            })
                        );
                    });
                    Promise.all(promises).then(models => {
                        resolve(
                            models.filter(
                                model =>
                                    model && model.predictions.test.length > 0
                            )
                        );
                    });
                }
            });
        });
    }

    get_predictions(model_directory, filename) {
        const prediction_file_path = path.join(
            Config.MODEL_DIRECTORY,
            model_directory,
            "predictions",
            filename
        );
        return fs.promises.readFile(prediction_file_path, "utf8");
    }
}

module.exports = new ModelManager();
