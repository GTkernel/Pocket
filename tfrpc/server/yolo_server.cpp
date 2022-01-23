#include <stdio.h>
#include <unistd.h>

#include <atomic>
#include <thread>

#include <tensorflow/c/c_api.h>
#include <grpcpp/grpcpp.h>
#include <grpcpp/health_check_service_interface.h>
#include <grpcpp/ext/proto_server_reflection_plugin.h>

#include "yolo.grpc.pb.h"

using grpc::Server;
using grpc::ServerBuilder;
using grpc::ServerContext;
using grpc::Status;

using yolo_tf::HelloReply;
using yolo_tf::HelloRequest;
using yolo_tf::YoloTensorflowWrapper;

// Global Variables
// Global_Tensor_Dict = {}
// Object_Ownership = {}
// Connection_Set = set()
// Global_Graph_Dict = {}
// Global_Sess_Dict = {}

std::atomic<int> conv2d_count(0);
std::atomic<int> batch_norm_count(0);
std::atomic<int> leaky_re_lu_count(0);
std::atomic<int> zero_padding2d_count(0);
std::atomic<int> add_count(0);
std::atomic<int> lambda_count(0);

#if 0

// class YoloTensorflowServiceImpl final : public YoloTensorflowWrapper::Service
// {
//     Status SayHello(ServerContext *context, const HelloRequest *request,
//                     HelloReply *reply) override
//     {
//         std::string prefix("Hello ");
//         reply->set_message(prefix + request->name());
//         // std::cout << "is lock free?: " << conv2d_count.is_lock_free() << std::endl;
//         return Status::OK;
//     }

//     // Status Connect(ServerContext *context, const ConnectRequest *request, ConnectResponse *response) override
//     // {
//     //     reply->set_message();
//     //     return Status::OK;
//     // }

//     // Status Disconnect(ServerContext *context, const DisconnectRequest *request, DisconnectResponse *response) override
//     // {
//     //     reply->set_message();
//     //     return Status::OK;
//     // }

//     // Status CheckIfModelExist(ServerContext *context, const CheckModelExistRequest *request, CheckModelExistResponse *response) override
//     // {
//     //     reply->set_message();
//     //     return Status::OK;
//     // }

//     // Status callable_emulator(ServerContext *context, const CallRequest *request, CallResponse *response) override
//     // {
//     //     reply->set_message();
//     //     return Status::OK;
//     // }

//     // Status get_iterable_slicing(ServerContext *context, const SlicingRequest *request, SlicingResponse *response) override
//     // {
//     //     reply->set_message();
//     //     return Status::OK;
//     // }

//     // Status constant(ServerContext *context, const ConstantRequest *request, ConstantResponse *response) override
//     // {
//     //     reply->set_message();
//     //     return Status::OK;
//     // }

//     // Status config_experimental_list__physical__devices(ServerContext *context, const DeviceType *request, PhysicalDevices *response) override
//     // {
//     //     reply->set_message();
//     //     return Status::OK;
//     // }

//     // Status image_decode__image(ServerContext *context, const DecodeImageRequest *request, DecodeImageResponse *response) override
//     // {
//     //     reply->set_message();
//     //     return Status::OK;
//     // }

//     // Status expand__dims(ServerContext *context, const ExpandDemensionRequest *request, ExpandDemensionResponse *response) override
//     // {
//     //     reply->set_message();
//     //     return Status::OK;
//     // }

//     // Status keras_layers_Input(ServerContext *context, const InputRequest *request, InputResponse *response) override
//     // {
//     //     reply->set_message();
//     //     return Status::OK;
//     // }

//     // Status keras_Model(ServerContext *context, const ModelRequest *request, ModelResponse *response) override
//     // {
//     //     reply->set_message();
//     //     return Status::OK;
//     // }

//     // Status keras_layers_ZeroPadding2D(ServerContext *context, const ZeroPadding2DRequest *request, ZeroPadding2DResponse *response) override
//     // {
//     //     reply->set_message();
//     //     return Status::OK;
//     // }

//     // Status keras_layers_Conv2D(ServerContext *context, const Conv2DRequest *request, Conv2DResponse *response) override
//     // {
//     //     reply->set_message();
//     //     return Status::OK;
//     // }

//     // Status keras_layers_LeakyReLU(ServerContext *context, const LeakyReluRequest *request, LeakyReluResponse *response) override
//     // {
//     //     reply->set_message();
//     //     return Status::OK;
//     // }

//     // Status keras_layers_Add(ServerContext *context, const AddRequest *request, AddResponse *response) override
//     // {
//     //     reply->set_message();
//     //     return Status::OK;
//     // }

//     // Status keras_layers_Lambda(ServerContext *context, const LambdaRequest *request, LambdaResponse *response) override
//     // {
//     //     reply->set_message();
//     //     return Status::OK;
//     // }

//     // Status keras_layers_UpSampling2D(ServerContext *context, const UpSampling2DRequest *request, UpSampling2DResponse *response) override
//     // {
//     //     reply->set_message();
//     //     return Status::OK;
//     // }

//     // Status keras_layers_Concatenate(ServerContext *context, const ConcatenateRequest *request, ContcatenateResponse *response) override
//     // {
//     //     reply->set_message();
//     //     return Status::OK;
//     // }

//     // Status image_resize(ServerContext *context, const ImageResizeRequest *request, ImageResizeResponse *response) override
//     // {
//     //     reply->set_message();
//     //     return Status::OK;
//     // }

//     // Status keras_regularizers_l2(ServerContext *context, const l2Request *request, l2Response *response) override
//     // {
//     //     reply->set_message();
//     //     return Status::OK;
//     // }

//     // Status attribute_tensor_shape(ServerContext *context, const TensorShapeRequest *request, TensorShapeResponse *response) override
//     // {
//     //     reply->set_message();
//     //     return Status::OK;
//     // }

//     // Status attribute_model_load__weight(ServerContext *context, const LoadWeightsRequest *request, LoadWeightsResponse *response) override
//     // {
//     //     reply->set_message();
//     //     return Status::OK;
//     // }

//     // Status attribute_checkpoint_expect__partial(ServerContext *context, const ExpectPartialRequest *request, ExpectPartialResponse *response) override
//     // {
//     //     reply->set_message();
//     //     return Status::OK;
//     // }

//     // Status tensor_op_divide(ServerContext *context, const DivideRequest *request, DivideResponse *response) override
//     // {
//     //     reply->set_message();
//     //     return Status::OK;
//     // }

//     // Status iterable_indexing(ServerContext *context, const IndexingRequest *request, IndexingResponse *response) override
//     // {
//     //     reply->set_message();
//     //     return Status::OK;
//     // }

//     // Status byte_tensor_to_numpy(ServerContext *context, const TensorToNumpyRequest *request, TensorToNumPyResponse *response) override
//     // {
//     //     reply->set_message();
//     //     return Status::OK;
//     // }

//     // Status get_object_by_id(ServerContext *context, const GetObjectRequest *request, GetObjectResponse *response) override
//     // {
//     //     reply->set_message();
//     //     return Status::OK;
//     // }

//     // Status batch_normalization(ServerContext *context, const BatchNormRequest *request, BatchNormResponse *response) override
//     // {
//     //     reply->set_message();
//     //     return Status::OK;
//     // }
// };

// void RunServer()
// {
//     std::string server_address("0.0.0.0:1990");
//     YoloTensorflowServiceImpl service;

//     grpc::EnableDefaultHealthCheckService(true);
//     grpc::reflection::InitProtoReflectionServerBuilderPlugin();
//     ServerBuilder builder;
//     // Listen on the given address without any authentication mechanism.
//     builder.AddListeningPort(server_address, grpc::InsecureServerCredentials());
//     // Register "service" as the instance through which we'll communicate with
//     // clients. In this case it corresponds to an *synchronous* service.
//     builder.RegisterService(&service);
//     // Finally assemble the server.
//     std::unique_ptr<Server> server(builder.BuildAndStart());
//     std::cout << "Server listening on " << server_address << std::endl;

//     // Wait for the server to shutdown. Note that some other thread must be
//     // responsible for shutting down the server for this call to ever return.
//     server->Wait();
// }
#endif
int main(int argc, char *argv[])
{
    printf("hello world!\n");
    printf("Hello from TensorFlow C library version %s\n", TF_Version());
    // RunServer();
    return 0;
}