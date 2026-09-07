// A loopback-only probe: request handler arrivals are separate from grpcurl errors.
package main

import (
	"context"
	"fmt"
	"net"
	"os"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/types/known/wrapperspb"
)

func main() {
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		panic(err)
	}
	arrivals, err := os.OpenFile(os.Args[1], os.O_WRONLY|os.O_CREATE|os.O_APPEND, 0600)
	if err != nil {
		panic(err)
	}
	defer arrivals.Close()
	server := grpc.NewServer()
	server.RegisterService(&grpc.ServiceDesc{
		ServiceName: "fixture.Audit",
		HandlerType: (*interface{})(nil),
		Methods: []grpc.MethodDesc{{MethodName: "Read", Handler: func(_ interface{}, ctx context.Context, decode func(interface{}) error, _ grpc.UnaryServerInterceptor) (interface{}, error) {
			// The fixture's field 1 has StringValue's wire encoding; protoc is unnecessary.
			request := &wrapperspb.StringValue{}
			if err := decode(request); err != nil {
				return nil, err
			}
			fmt.Fprintln(arrivals, request.Value)
			if request.Value == "bad" {
				return nil, status.Error(codes.InvalidArgument, "server validation")
			}
			if request.Value == "wait" {
				select {
				case <-ctx.Done():
					return nil, status.Error(codes.DeadlineExceeded, "server deadline")
				case <-time.After(time.Second):
				}
			}
			return &wrapperspb.StringValue{Value: request.Value}, nil
		}}},
	}, struct{}{})
	fmt.Println(listener.Addr())
	if err := server.Serve(listener); err != nil {
		panic(err)
	}
}
